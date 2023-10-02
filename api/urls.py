from django.urls import path
from .views import AppUserCreateView, LoanCreateView, MakePaymentView, GetStatementView

urlpatterns = [
    path('register-user/', AppUserCreateView.as_view()),
    path('apply-loan/', LoanCreateView.as_view()),
    path('make-payment/', MakePaymentView.as_view()),
    path('get-statement/<int:loan_id>', GetStatementView.as_view()),
]
