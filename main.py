from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory='static'), name='static')

templates = Jinja2Templates(directory='templates')


transactions = [
    {
        'id': 1,
        'user_id': 12,
        'type': 'Buy',
        'date': '2026-01-10',
        'name': 'Apple Inc.',
        'units': 10,
        'rate': 185.50,
    },
    {
        'id': 2,
        'user_id': 12,
        'type': 'Sell',
        'date': '2026-01-28',
        'name': 'Tesla',
        'units': 5,
        'rate': 215.00,
    },
    {
        'id': 3,
        'user_id': 12,
        'type': 'Buy',
        'date': '2026-02-14',
        'name': 'Google',
        'units': 3,
        'rate': 2750.00,
    },
    {
        'id': 4,
        'user_id': 12,
        'type': 'Buy',
        'date': '2026-03-01',
        'name': 'NVIDIA',
        'units': 8,
        'rate': 875.25,
    },
    {
        'id': 5,
        'user_id': 15,
        'type': 'Buy',
        'date': '2026-01-05',
        'name': 'Microsoft',
        'units': 6,
        'rate': 320.00,
    },
    {
        'id': 6,
        'user_id': 15,
        'type': 'Sell',
        'date': '2026-02-20',
        'name': 'Amazon',
        'units': 4,
        'rate': 3450.00,
    },
    {
        'id': 7,
        'user_id': 15,
        'type': 'Buy',
        'date': '2026-02-25',
        'name': 'Meta',
        'units': 12,
        'rate': 490.75,
    },
    {
        'id': 8,
        'user_id': 15,
        'type': 'Sell',
        'date': '2026-03-05',
        'name': 'Netflix',
        'units': 7,
        'rate': 610.00,
    },
]


@app.get('/transactions')
def get_all_transactions(request: Request):
    return templates.TemplateResponse(request,
                                      name='transactions.html',
                                      context={'transactions': transactions})


@app.get('/', name='home')
def home(request: Request):
    return {'message': 'This is home route'}

# API transaction endpoint
@app.get('/api/transactions/{id}')
def get_transactions(id: int):
    for tr in transactions:
        if tr['id'] == id:
            return tr
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                        detail='Transaction not found.')

@app.get('/api/user_transactions/{user_id}')
def get_user_transactions_api(user_id: int) -> list[dict]:
    result = []
    for tr in transactions:
        if tr['user_id'] == user_id:
            result.append(tr)
        
    return result


@app.get('/user_transactions/{user_id}')
def get_user_transactions(request: Request, user_id: int):
    result = [tr for tr in transactions if tr['user_id'] == user_id]
    return templates.TemplateResponse(request,
                                      name='transactions.html',
                                      context={'transactions': result, 'user_id': user_id})


