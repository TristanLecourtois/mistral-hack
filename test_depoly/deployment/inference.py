import torch
import json
import os
from model import MyModel

def model_fn(model_dir):
    model = MyModel()
    model_path = os.path.join(model_dir, "model.pth")
    model.load_state_dict(torch.load(model_path))
    model.eval()
    return model

def input_fn(request_body, request_content_type):
    data = json.loads(request_body)
    return torch.tensor(data, dtype=torch.float32)

def predict_fn(input_data, model):
    with torch.no_grad():
        prediction = model(input_data)
    return prediction.numpy().tolist()

def output_fn(prediction, content_type):
    return json.dumps(prediction)