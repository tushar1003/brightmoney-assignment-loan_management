from celery import shared_task
import pandas as pd
from .models import AppUser
from loan.settings import BASE_DIR

@shared_task
def set_credit_score(user):
    user = AppUser.objects.get(pk=user)
    
    file = str(BASE_DIR / 'transactions.csv')
    
    df = pd.read_csv(file, delimiter=',')
    
    df.columns = ['aadhar_id', 'date', 'transaction_type', 'amount']
    df = df.loc[df['aadhar_id'] == user.aadhar]
    
    credits = df.loc[df['transaction_type'] == 'CREDIT']
    debits = df.loc[df['transaction_type'] == 'DEBIT']
    balance = credits['amount'].sum() - debits['amount'].sum()
    
    if balance >= 1000000:
        credit_score = 900
    elif balance <= 100000:
        credit_score = 300
    else:
        credit_score = 300 + ((balance - 100000) // 15000) * 10 
    
    user.credit_score = credit_score
    user.save()
