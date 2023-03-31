from app.utils import catch_exceptions,download_from_s3
import os
import re
import nltk
nltk.download('wordnet')
nltk.download('stopwords')
from nltk.stem import WordNetLemmatizer
from constants import STOP_WORDS,punctuations
import json
import logging
logger = logging.getLogger(name=__name__)

class ExtractAttributes(object):
    def __init__(self):
        pass
    
    def lemmatize_text(self,text):
        try:
            lemmatizer = WordNetLemmatizer()
            lemmatized_list = [lemmatizer.lemmatize(word.lower()) for word in text.split(' ') if word.lower() not in STOP_WORDS]
            lem_string = ' '.join(lemmatized_list).strip().lower()
            return lem_string
        except Exception as e:
            logger.error(e,exc_info=True)
    
    @catch_exceptions
    def unpunctuate(self,text):
        try:
            text = str(text)
            text = text.replace("'s","")
            unpunctuated_list = [character if character not in punctuations else ' ' for character in text]
            unpunctuated_text = "".join(unpunctuated_list)
            return unpunctuated_text
        except Exception as e:
            logger.error(e,exc_info=True)
                        
    @catch_exceptions
    def clean_text(self,text):
        try:
            text = self.lemmatize_text(text) #lemmatize the input text
            text = self.unpunctuate(text)
            return text
        except Exception as e:
            logger.error(e,exc_info=True)
            
    
    
    @catch_exceptions
    def get_valid_values(self):
        try:
            valid_values_path = self.check_valid_values_file_exists('valid_values_updated.json')
            with open(valid_values_path,'r') as f:
                valid_values = json.load(f)
            return valid_values
        except Exception as e:
            logger.error(e,exc_info=True)
            
    @catch_exceptions
    def search_entity(self, attribute_value, product_data):
        try:
            if re.search(r"\b" + re.escape(attribute_value) + r"\b", product_data) and attribute_value!='':
                return True #ref: "https://stackoverflow.com/questions/4154961/find-substring-in-string-but-only-if-whole-words"
            return False
        except Exception as e:
            logger.error(e,exc_info=True)
            
    @catch_exceptions
    def extract_attributes(self, request_data):
        try:
            valid_values = self.get_valid_values()
            attribute_names = list(valid_values.get(str(request_data["category_id"])).get(str(request_data["sub_category_id"])).get("valid_values").keys()) #get the list of all the valid attribute names
            text_attributes = {}
            title = self.clean_text(request_data["product_title"])
            for each_attribute_values in attribute_names:
                    if each_attribute_values:
                        for each_attr_value in each_attribute_values:
                            is_true = self.search_entity(self.clean_text(each_attr_value), title)
                            if is_true:
                                if each_attribute_values in text_attributes.keys():
                                    pass
                                else:
                                    text_attributes[each_attribute_values] = each_attr_value
                            else:
                                pass
            return text_attributes
        except Exception as e:
            logger.error(e,exc_info=True)
        
    @catch_exceptions
    def get_attributes(self, request_data):
        #to manage multiple product_titles
        try:
            product_titles = request_data["product_title"]
            all_titles_attributes = []
            for each_title in product_titles:
                request_data["product_title"] = each_title
                each_title_attributes = self.extract_attributes(request_data)
                all_titles_attributes.append(each_title_attributes)
            return all_titles_attributes
        except Exception as e:
            logger.error(e,exc_info=True)
            
    @catch_exceptions
    def get_attributes_for_a_string(self,request_data):
        try:
            response_data = {}
            mandatory_fields = ["product_title", "category_id","sub_category_id"]
            for field in mandatory_fields:
                if not field in request_data["data"]:
                    response_data = {
                        "status":False,
                        "message":"Required field is missing",
                        "error_obj":{
                            "description":"{} is missing".format(field),
                            "error_code":"REQUIRED_FIELD_IS_MISSING"
                        }
                    }
            if not response_data:
                response_data = {
                    "status":True,
                    "data":{
                        "product_details":self.get_attributes(request_data["data"])
                    }
                }
            return response_data
        except Exception as e:
            logger.error(e,exc_info=True)
            
ExtractedAttributes = ExtractAttributes()
