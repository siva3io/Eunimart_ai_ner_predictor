import logging
from flask import Blueprint, jsonify, request
from app.services.ner import ExtractedAttributes
from app.services.ner import AttributeValues

ner_prediction = Blueprint('ner_prediction', __name__)

logger = logging.getLogger(__name__)

@ner_prediction.route('/get_attribute_values', methods=['POST'])
def get_attribute_values():
    request_data = request.get_json()
    
    data = AttributeValues.get_attribute_values(request_data)
    if not data:
        data = {}
    return jsonify(data)

@ner_prediction.route('/extract_attribute_values', methods=['POST'])
def get_attributes_for_a_string():
    request_data = request.get_json()
    
    data = ExtractedAttributes.get_attributes_for_a_string(request_data)
    if not data:
        data = {}
    return jsonify(data)
