from django.db import models
from datetime import datetime
from .constants import LOAN_RATES

class AppUser(models.Model):
    aadhar = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    email = models.EmailField(null=False)
    annual_income = models.IntegerField(null=False)
    credit_score = models.IntegerField(default=300)

    def __str__(self):
        return self.name

LOAN_CHOICES = [
    ('CAR', 'CAR'),
    ('HOME', 'HOME'),
    ('EDUCATION', 'EDUCATION'),
    ('PERSONAL', 'PERSONAL'),
]

class Loan(models.Model):
    user = models.ForeignKey('AppUser', on_delete=models.CASCADE)
    loan_type = models.CharField(choices=LOAN_CHOICES, max_length=20)
    loan_amount = models.IntegerField(null=False)
    interest_rate = models.FloatField(blank=True, null=True)
    term_period = models.IntegerField(null=False)
    disbursement_date = models.DateField(null=False)
    total_repayable = models.IntegerField(blank=True, null=True)
    active = models.BooleanField(default=True)
    emi = models.ForeignKey('EMI', on_delete=models.DO_NOTHING, null=True)

    def __str__(self):
        return f'{self.user.name} {self.loan_type} {self.loan_amount}'

    @classmethod
    def create_loan(self, data):
        # ['user', 'loan_type', 'loan_amount', 'term_period', 'disbursement_date']
        data['interest_rate'] = LOAN_RATES[data['loan_type']]
        loan = Loan.objects.create(**data)
        return loan

    def set_emi(self):
        flat_interest_rate = self.interest_rate ** (self.term_period/12)

        if flat_interest_rate < 1.014:
            raise Exception('total interest lower than 14%')
        
        total_interest_amount = flat_interest_rate * self.loan_amount

        if total_interest_amount <= 10000:
            raise Exception('total interest lower than 10000 Rs')
        
        total_repayable = total_interest_amount + self.loan_amount
        monthly_emi = total_repayable // self.term_period
        last_emi = total_repayable % self.term_period
        
        if monthly_emi > 0.05 * self.user.annual_income: #60% of monthly income = 5% of annual income
            raise Exception('monthly emi more than 60% of monthly income')
        
        due_date = self.disbursement_date
        if due_date.day != 1:
            due_date = due_date.replace(day = 1)
            due_date = due_date.replace(month = due_date.month + 1)
        
        emi = EMI.objects.create(total_tenure=self.term_period, flat_interest=flat_interest_rate, emi_amount=monthly_emi, last_emi_amount=last_emi, amount_paid=0, next_due_date=due_date, paid_terms=0, emi_due=0)

        self.total_repayable = total_repayable
        self.emi = emi
        self.save()

        return emi
    
    def recalculate_emi(self):
        emi = self.emi
        total_repayable = self.total_repayable - emi.amount_paid
        monthly_emi = total_repayable // (emi.total_tenure - emi.paid_terms)
        last_emi = total_repayable % (emi.total_tenure - emi.paid_terms)
        
        if monthly_emi > 0.05 * self.user.annual_income: #60% of monthly income = 5% of annual income
            raise Exception('monthly emi more than 60% of monthly income')
        
        emi.last_emi_amount = last_emi
        emi.emi_amount = monthly_emi
        emi.save()

        return emi
        

class EMI(models.Model):
    total_tenure = models.IntegerField(null=False)
    flat_interest = models.FloatField(null=False)
    emi_amount = models.IntegerField(null=False)
    last_emi_amount = models.IntegerField(null=False)
    amount_paid = models.IntegerField(null=False)
    next_due_date = models.DateField(null=False)
    paid_terms = models.IntegerField(null=False)
    emi_due = models.IntegerField(null=False)

class Transaction(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE)
    date = models.DateField(default=datetime.now)
    emi_date = models.DateField(null=False)
    amount_paid = models.IntegerField(null=False)
    emi_term = models.IntegerField(null=False)
    principal = models.IntegerField(null=False)
    interest = models.FloatField(null=False)