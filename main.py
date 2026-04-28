from enum import Enum
from fastapi import FastAPI

app = FastAPI()

class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"

@app.get("/")
def main():
    return {"message": "Hello this is World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    match(model_name):
        case ModelName.alexnet:
            return {"model_name": model_name, "message": "Deep Learning FTW!"}

        case ModelName.lenet:
            return {"model_name": model_name, "message": "LeCNN all the images"}
        
        case ModelName.resnet:
            return {"model_name": model_name, "message": "Have some residuals"}

        case _:
            return ("Not accepted choice")
    