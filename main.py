from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from schema import CreateTransaction, ResponseTransaction, TypeEnum
app = FastAPI()

BUY, SELL = TypeEnum.BUY, TypeEnum.SELL

app.mount("/static", StaticFiles(directory='static'), name='static')
app.mount('/media', StaticFiles(directory='media'), name='media')

templates = Jinja2Templates(directory='templates')


transactions: list[dict] = [
    {
        'id': 1,
        'user_id': 12,
        'type': BUY,
        'date': '2026-01-10',
        'entity_name': 'Apple Inc.',
        'units': 10,
        'rate': 185.50,
    },
    {
        'id': 2,
        'user_id': 12,
        'type': SELL,
        'date': '2026-01-28',
        'entity_name': 'Tesla',
        'units': 5,
        'rate': 215.00,
    },
    {
        'id': 3,
        'user_id': 12,
        'type': BUY,
        'date': '2026-02-14',
        'entity_name': 'Google',
        'units': 3,
        'rate': 2750.00,
    },
    {
        'id': 4,
        'user_id': 12,
        'type': BUY,
        'date': '2026-03-01',
        'entity_name': 'NVIDIA',
        'units': 8,
        'rate': 875.25,
    },
    {
        'id': 5,
        'user_id': 15,
        'type': BUY,
        'date': '2026-01-05',
        'entity_name': 'Microsoft',
        'units': 6,
        'rate': 320.00,
    },
    {
        'id': 6,
        'user_id': 15,
        'type': SELL,
        'date': '2026-02-20',
        'entity_name': 'Amazon',
        'units': 4,
        'rate': 3450.00,
    },
    {
        'id': 7,
        'user_id': 15,
        'type': BUY,
        'date': '2026-02-25',
        'entity_name': 'Meta',
        'units': 12,
        'rate': 490.75,
    },
    {
        'id': 8,
        'user_id': 15,
        'type': SELL,
        'date': '2026-03-05',
        'entity_name': 'Netflix',
        'units': 7,
        'rate': 610.00,
    },
]

# ----------------- HTML ENDPOINTS --------------- # 

@app.get('/', name='home', include_in_schema=False)
def home_page(request: Request):
    return templates.TemplateResponse(request, 
                                      name='home.html')

@app.get('/user', name='home', include_in_schema=False)
def user_home_page(request: Request):
    # TODO : Implement home page for logged in user
    pass

# All transactions
@app.get('/transactions', include_in_schema=False)
def all_transactions(request: Request):
    return templates.TemplateResponse(request,
                                      name='transactions.html',
                                      context={'transactions': transactions})


@app.get('/user_transactions/{user_id}', include_in_schema=False, name='user_transactions')
def user_transactions_page(request: Request, user_id: int):
    result = [tr for tr in transactions if tr['user_id'] == user_id]
    if not result:
        return templates.TemplateResponse(request,
                                          name='error.html', 
                                          context={'status_code': status.HTTP_404_NOT_FOUND, 
                                                   'message': 'Resource not found'})
    return templates.TemplateResponse(request,
                                      name='transactions.html',
                                      context={'transactions': result, 'user_id': user_id})



# --------------- API ENDPOINTS -------------------------#


# Get transaction by id
@app.get('/api/transactions/{id}', response_model=ResponseTransaction)
def get_transaction_api(id: int):
    # TODO   
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                        detail='Transaction not found.')

# Get all transaction of specific user 
@app.get('/api/user_transactions/{user_id}', response_model=list[ResponseTransaction])
def get_user_transactions_api(user_id: int) -> list[dict]:
    pass


# Get all transactions
@app.get('/api/transactions', response_model=list[ResponseTransaction])
def get_all_transactions_api(request: Request):
    return transactions




# --------- EXCEPTION HANDLERS --------------------------# 

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(request,
                                      name='error.html',
                                      status_code=status.HTTP_404_NOT_FOUND,
                                      context={'status_code': status.HTTP_404_NOT_FOUND,
                                               'message': 'Page not found'})
