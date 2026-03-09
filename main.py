from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from schema import CreateTransaction, ResponseTransaction, TypeEnum
app = FastAPI()

STATIC_DIR = Path(__file__).resolve().parent / "static"
BUY, SELL = TypeEnum.BUY, TypeEnum.SELL

app.mount("/static", StaticFiles(directory='static'), name='static')

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

@app.get('/', name='home', include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request, 
                                      name='home.html')

@app.get('/transactions', include_in_schema=False)
def get_all_transactions(request: Request):
    return templates.TemplateResponse(request,
                                      name='transactions.html',
                                      context={'transactions': transactions})


@app.get('/user_transactions/{user_id}', include_in_schema=False)
def get_user_transactions(request: Request, user_id: int):
    result = [tr for tr in transactions if tr['user_id'] == user_id]
    return templates.TemplateResponse(request,
                                      name='transactions.html',
                                      context={'transactions': result, 'user_id': user_id})

# API transaction endpoint
@app.get('/api/transactions/{id}', response_model=ResponseTransaction)
def get_transactions(id: int):
    for tr in transactions:
        if tr['id'] == id:
            return tr
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                        detail='Transaction not found.')

@app.get('/api/user_transactions/{user_id}', response_model=list[ResponseTransaction])
def get_user_transactions_api(user_id: int) -> list[dict]:
    result = []
    for tr in transactions:
        if tr['user_id'] == user_id:
            result.append(tr)
        
    return result



@app.get('/api/transactions', response_model=list[ResponseTransaction])
def get_all_transactions_api(request: Request):
    return transactions