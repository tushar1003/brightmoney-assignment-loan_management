from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import AppUserSerializer, LoanSerializer, MakePaymentSerializer
from .models import AppUser, Loan, Transaction
from .constants import LOAN_MAXIMUMS
from .tasks import set_credit_score

class AppUserCreateView(APIView):
    serializer_class = AppUserSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({'Error': 'invalid data'}, status=HTTP_400_BAD_REQUEST)
        
        try:
            user = AppUser.objects.create(**serializer.validated_data)
            set_credit_score.delay(user.pk)
        except Exception as E:
            return Response({'Error': f'failed to save user / {E}'}, status=HTTP_400_BAD_REQUEST)
        
        return Response({'id': user.id}, status=HTTP_200_OK)

class LoanCreateView(APIView):
    serializer_class = LoanSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({'Error': 'invalid data'}, status=HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data

        user = data['user']
        
        if not user.credit_score >= 450:
            return Response({'Error': 'insufficient credit score'}, status=HTTP_400_BAD_REQUEST)
        
        if not user.annual_income >= 150000:
            return Response({'Error': 'insufficient annual income'}, status=HTTP_400_BAD_REQUEST)
        
        if data['loan_amount'] > LOAN_MAXIMUMS[data['loan_type']]:
            return Response({'Error': 'loan amount exceeded limit'}, status=HTTP_400_BAD_REQUEST)

        try:
            loan = Loan.create_loan(data)
        except Exception as E:
            return Response({'Error': f'failed to save loan / {E}'}, status=HTTP_400_BAD_REQUEST)
        
        try:
            emi = loan.set_emi()
        except Exception as E:
            loan.delete()
            return Response({'error': f'failed to calculate emi / {E}'}, status=HTTP_400_BAD_REQUEST)
        
        due_dates = []
        date = emi.next_due_date
        for i in range(emi.total_tenure - emi.paid_terms - 2):
            due_dates.append({'date': date.strftime('%d-%m-%Y'), 'amount_due': emi.emi_amount})
            if(date.month == 12):
                date = date.replace(month=1, year=date.year + 1)
            else:
                date = date.replace(month=date.month + 1)
        due_dates.append({'date': date.strftime('%d-%m-%Y'), 'amount_due': emi.last_emi_amount})

        return Response({'id': loan.pk, 'due_dates': due_dates}, status=HTTP_200_OK)

class MakePaymentView(APIView):
    serializer_class = MakePaymentSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({'Error': 'invalid data'}, status=HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data

        loan = data['loan']

        emi = loan.emi
        if not emi:
            return Response({'Error': 'emi details not found'}, status=HTTP_400_BAD_REQUEST)

        emi_date = emi.next_due_date

        if emi.emi_due != 0:
            data['amount_paid'] -= emi.emi_due
            emi.amount_paid += emi.emi_due
            if emi.next_due_date.month == 12:
                emi.next_due_date = emi.next_due_date.replace(month = 1, year = emi.next_due_date.year + 1)
            else:
                emi.next_due_date = emi.next_due_date.replace(month = emi.next_due_date.month + 1)
            emi.paid_terms += 1
            emi.emi_due = 0
        
        if data['amount_paid'] < (emi.emi_amount if emi.paid_terms + 1 < emi.total_tenure else emi.last_emi_amount):
            emi.emi_due = emi.emi_amount - data['amount_paid']
            emi.amount_paid += data['amount_paid']
            emi.save()
        else:
            emi.amount_paid += data['amount_paid']
            emi.paid_terms += 1
            if emi.next_due_date.month == 12:
                emi.next_due_date = emi.next_due_date.replace(month = 1, year = emi.next_due_date.year + 1)
            else:
                emi.next_due_date = emi.next_due_date.replace(month = emi.next_due_date.month + 1)
            emi.save()
            if emi.paid_terms == emi.total_tenure:
                loan.active = False
                loan.save()
            if data['amount_paid'] > (emi.emi_amount if emi.paid_terms < emi.total_tenure else emi.last_emi_amount):
                try:
                    loan.recalculate_emi()
                except Exception as E:
                    return Response({'Error': f'failed to recalculate emi / {E}'}, status=HTTP_400_BAD_REQUEST)
                
        transaction = Transaction.objects.filter(loan=loan).order_by('-date')
        if not transaction:
            transaction = Transaction.objects.create(loan=loan, emi_date=emi_date, amount_paid=data['amount_paid'], emi_term=1, principal=loan.loan_amount, interest=loan.interest_rate)
        else:
            transaction = Transaction.objects.create(loan=loan, emi_date=emi_date, amount_paid=data['amount_paid'], emi_term=emi.paid_terms+1, principal=loan.loan_amount, interest=loan.interest_rate)
                
        return Response({}, status=HTTP_200_OK)
    
class GetStatementView(APIView):

    def get(self, request, loan_id):
        try:
            loan = Loan.objects.get(pk=loan_id)
        except Exception as E:
            return Response({'Error': f'failed to fetch loan / {E}'}, status=HTTP_400_BAD_REQUEST)
        
        transactions = Transaction.objects.filter(loan=loan).order_by('date').values('emi_date' ,'amount_paid', 'principal', 'interest')
        
        emi = loan.emi
        due_dates = []
        date = emi.next_due_date
        flag = emi.emi_due != 0
        for i in range(emi.total_tenure - emi.paid_terms - 2):
            if flag:
                due_dates.append({'date': date.strftime('%d-%m-%Y'), 'amount_due': emi.emi_amount + emi.emi_due})
                flag = False
            else:
                due_dates.append({'date': date.strftime('%d-%m-%Y'), 'amount_due': emi.emi_amount})

            if(date.month == 12):
                date = date.replace(month=1, year=date.year + 1)
            else:
                date = date.replace(month=date.month + 1)
        due_dates.append({'date': date.strftime('%d-%m-%Y'), 'amount_due': emi.last_emi_amount})

        return Response({'Past_Transactions': transactions, 'Upcoming_Transactions': due_dates}, status=HTTP_200_OK)



        
        

            

