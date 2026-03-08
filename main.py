from fastapi import FastAPI, Request

app = FastAPI()

@app.get('/')
def home(request: Request):
    return {'message': 'This is home route'}
