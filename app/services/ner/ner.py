from app.services.ner.extract_attributes import ExtractedAttributes
from constants import channel_id_name_mapping, model_mapping
from sklearn.feature_extraction.text import CountVectorizer
from app.utils import catch_exceptions,download_from_s3
from app.models.products import Products
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
from config import Config
import requests
import logging
import pickle
import spacy
import json
import yake
import os
import re

logger = logging.getLogger(name=__name__)

class GetAttributeValues(object):
    def __init__(self):
        pass

    @catch_exceptions
    def keywords_check_file_exists(self,request_data,file_name):
        try:
            folder_name = channel_id_name_mapping.get(request_data["channel_id"]) #get what model for what marketplace
            abs_file_path = "ai-models/"+folder_name+'/'+file_name
            s3_path = 'ner_models/' + folder_name+'/'+ request_data['category_name'] + '_' + file_name
            if not os.path.exists(abs_file_path):
                os.makedirs("/".join(abs_file_path.split('/')[:-1]), exist_ok=True)
                download_from_s3(s3_path,abs_file_path)
            return abs_file_path
        except Exception as e:
            logger.error(e,exc_info=True)

    @catch_exceptions
    def pre_process(self,text):
        text=text.lower()
        text=re.sub("</?.*?>"," <> ",text)
        text=re.sub("(\\d|\\W)+"," ",text)
        ls=WordNetLemmatizer()
        text=ls.lemmatize(text)
        return text

    @catch_exceptions
    def extract_topn_from_vector(self,feature_names, sorted_items, topn=10):   
        sorted_items = sorted_items[:topn]
        score_vals = []
        feature_vals = []
        for idx, score in sorted_items:
            score_vals.append(round(score, 3))
            feature_vals.append(feature_names[idx])
        results= {}
        for idx in range(len(feature_vals)):
            results[feature_vals[idx]]=score_vals[idx]
            # print(score_vals)
        return results.keys()

    @catch_exceptions
    def check_file_exists(self,request_data,file_name):
        try:
            folder_name = model_mapping.get(request_data["channel_id"]) #get what model for what marketplace
            abs_file_path = "ai-models/"+folder_name+'/'+file_name
            s3_path = 'ner_models/' + folder_name+'/'+file_name
            if not os.path.exists(abs_file_path):
                os.makedirs("/".join(abs_file_path.split('/')[:-1]), exist_ok=True)
                download_from_s3(s3_path,abs_file_path)
            return abs_file_path
        except Exception as e:
            logger.error(e,exc_info=True)

    @catch_exceptions
    def sort_coo(self,coo_matrix):
        tuples = zip(coo_matrix.col, coo_matrix.data)
        return sorted(tuples, key=lambda x: (x[1], x[0]), reverse=True)

    @catch_exceptions
    def get_keywords(self,request_data):
        try:
            vectorizer_path = self.keywords_check_file_exists(request_data,'vectorizer.pickle')
            vectorizer = pickle.load(open(vectorizer_path,'rb'))
            stop_words = stopwords.words('english')
            model_path = self.keywords_check_file_exists(request_data,'tfidf_transformer.pickle')
            tfidf_transformer = pickle.load(open(model_path,'rb'))
            tf_idf_vector = tfidf_transformer.transform(
                vectorizer.transform(
                    [
                        self.pre_process(" ".join(request_data["cleaned_similar_product_titles"]))
                    ]
                    )
                )
            feature_names=vectorizer.get_feature_names()
            sorted_items = self.sort_coo(tf_idf_vector.tocoo())
            keywords = self.extract_topn_from_vector(feature_names,sorted_items,10)           
            return keywords
        except Exception as e:
            logger.error(e,exc_info=True)
    
    @catch_exceptions
    def get_similar_products(self,request_data):
        try:
            similar_products = [request_data['product_title'], request_data["highlights"]] #first we find the attributes from the title and then we find the attributes from similar products            
            if "similar_products" in request_data.keys():
                load_cloumns = [Products.product_title]
                result = Products.smart_query(filters={
                    "marketplace__exact":request_data["marketplace"],
                    "fid__in":request_data["similar_products"]
                }).with_entities(*load_cloumns).all()
                for product in result:
                    similar_products.append(product[0])
            return similar_products
        except Exception as e:
            logger.error(e,exc_info=True)  
            
    @catch_exceptions
    def load_model(self, request_data):
        try:
            supporting_file_names = ["/ner/cfg","/ner/model","/ner/moves","/vocab/key2row","/vocab/lookups.bin","/vocab/strings.json","/vocab/vectors","/meta.json","/tokenizer"]
            for file_name in supporting_file_names:
                self.check_file_exists(request_data, request_data["category_name"]+file_name)
            model_path = self.check_file_exists(request_data, request_data["category_name"])
            model = spacy.load(model_path)
            return model
        except Exception as e:
            logger.error(e,exc_info=True)
            
    @catch_exceptions
    def get_closed_attributes(self, request_data):
        try:
            closed_attributes = {}
            #get attriutes from the original product title
            request_data["product_title"] = [request_data["similar_product_titles"][0]]
            extracted_attributes = (ExtractedAttributes.get_attributes(request_data))[0]
            for each_attribute_name in extracted_attributes:
                closed_attributes[each_attribute_name] = extracted_attributes[each_attribute_name]
            #get attributes from similar products
            for title_index in range(1, len(request_data["similar_product_titles"])):
                request_data["product_title"] = [request_data["similar_product_titles"][title_index]]
                extracted_attributes = (ExtractedAttributes.get_attributes(request_data))[0] # [0]-> there will be only one item in the list, i.e the attributes dictionary
                for each_attribute_name in extracted_attributes:
                    if (each_attribute_name in closed_attributes.keys() or each_attribute_name=='color'):#we don't consider color attribute from similar products
                        pass
                    else:
                        closed_attributes[each_attribute_name] = extracted_attributes[each_attribute_name]
            return closed_attributes
        except Exception as e:
           logger.error(e,exc_info=True)

    @catch_exceptions
    def predict_attribute_values(self,request_data):
        '''
        the open value list(which are not fixed values, like brand) are found using spacy's ner,
        and closed value list is done by checking the attr values in the text.
        '''
        try:
            print("test")
            model = self.load_model(request_data)
            attribute_values = dict()            
            attributes = model(request_data["cleaned_similar_product_titles"][0]) #taking actual_product_title as input
            for attribute in attributes.ents:
                if attribute.label_.lower() == 'brand':
                    attribute_values[attribute.label_.lower()] = attribute.text 
            closed_attributes = self.get_closed_attributes(request_data)
            attribute_values.update(closed_attributes)
            attribute_values["keywords"] = ",".join(self.get_keywords(request_data))
            attribute_values["category_name"] = request_data["category_key"]
            attribute_values["sub_category_name"] = request_data["sub_category_key"]
            attribute_values["category_id"] = request_data["category_id"]
            attribute_values["sub_category_id"] = request_data["sub_category_id"]
            attribute_values["channel_id"] = "0"
            return attribute_values
        except Exception as e:
            logger.error(e,exc_info=True)

    @catch_exceptions
    def get_attribute_values(self,request_data):
        try:
            response_data = {}
            mandatory_fields = ["channel_id","category_key","sub_category_key","product_title", "category_id","sub_category_id", "highlights"]
            for field in mandatory_fields:
                if (not field in request_data["data"]) and (field=="highlights"):
                    request_data["data"]["highlights"] = ""
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
                get_hierarchy_obj = json.loads(requests.post(url = Config.GET_HIERARCHY_ENDPOINT,json= request_data).text)
                if get_hierarchy_obj["status"]:
                    request_data["data"].update(get_hierarchy_obj["data"])
                request_data["data"]["marketplace"] = channel_id_name_mapping.get(request_data["data"]["channel_id"])
                request_data["data"]["similar_product_titles"] = self.get_similar_products(request_data["data"])
                request_data["data"]["cleaned_similar_product_titles"] = [ExtractedAttributes.clean_text(title) for title in request_data["data"]["similar_product_titles"]]
                response_data = {
                    "status":True,
                    "data":{
                        "product_details":self.predict_attribute_values(request_data["data"])
                    }
                }
            return response_data
        except Exception as e:
            logger.error(e,exc_info=True)
            
AttributeValues = GetAttributeValues()
