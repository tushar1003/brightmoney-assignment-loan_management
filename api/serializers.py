from rest_framework import serializers
from .models import AppUser, Loan, Transaction

class AppUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppUser
        fields = ['aadhar', 'name', 'email', 'annual_income',]
        read_only_fields = ['id']



class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['user', 'loan_type', 'loan_amount', 'term_period', 'disbursement_date']

class MakePaymentSerializer(serializers.ModelSerializer):
    # loan_id = serializers.IntegerField()
    # amount = serializers.IntegerField()
    class Meta:
        model = Transaction
        fields = ['loan', 'amount_paid']

# class GetStatementSerializer(serializers.Serializer):
#     loan_id = serializers.IntegerField()