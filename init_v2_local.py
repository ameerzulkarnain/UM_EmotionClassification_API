import flask
import pickle
import numpy as np
import pymysql
import os
from tensorflow.python.keras.preprocessing import sequence as keras_seq
from tensorflow.python.keras.models import load_model
from flask import request, jsonify
import warnings

#   UM_EmotionIdentification_API
import xgboost as xgb
import pandas as pd
import json

#   Import ARI
import textstat

global tokenizer
global pred_models 
global result
global INPUT_SIZE
global error

app = flask.Flask(__name__)
app.config["DEBUG"] = True
app.config['JSON_SORT_KEYS'] = False
warnings.filterwarnings('ignore')
tokenizer = None
error = None

pred_models = {}
INPUT_SIZE = {'word2seq_cnn':700}

table_name = {'word2seq_cnn':'Word2Seq_CNN'}

WORDS_SIZE = 10001
retName = ['Predicted_emotion','Predicted_emotion_value', 'Probability_afraid','Probability_anger','Probability_bored','Probability_excited','Probability_happy', 'Probability_relax', 'Probability_sad','Probability_worry']

feature = []

#   Cannot add worry as there is no user with worry data label yet
header = ['total_tweet','afraid_percent','anger_percent','bored_percent','excited_percent','happy_percent','relax_percent','sad_percent','avg_length','avg_ari','avg_char','std_dev','afraid_prob','anger_prob','bored_prob','excited_prob','happy_prob','relax_prob','sad_prob']

retName_v2 = ['Probability_afraid','Probability_anger','Probability_bored','Probability_excited','Probability_happy', 'Probability_relax', 'Probability_sad','Probabiliity_worry']


model = 'word2seq_cnn'
pred_models={'word2seq_cnn' : load_model('./Models/word2seq_cnn.hdf5')}
pred_models[model]._make_predict_function()
## Loading the Keras Tokenizer sequence file
with open('./pickle/tokenizer.pickle', 'rb') as handle:
    tokenizer = pickle.load(handle)

@app.route('/', methods=['GET'])
def index():
    return "<h1>Hello</h1>"

## Main API get hook function
@app.route('/api/v1/emotion', methods=['POST'])
def api_sentiment():
    global error
    error = False
    
    if 'text' in request.json:
        text = request.json['text']
        print (text,flush=True)
        if text == '':
            return "Error: No text provideed. Please specify a text."
        result = predict(text)
        return(jsonify(result))
    
    elif 'data' in request.json:
        data = request.json['data']
        if data == '':
            return "Error: No data provided. Please specify your data."
        analyse_result = analyse(data)
        return(jsonify(analyse_result))
    
    else:
        error = True
        return "Error: No text field provided. Please specify a text."

def predict(text):
    # global pred_models

    return_dict={}
    
    ## Tokkenizing test data and create matrix
    list_tokenized_test = tokenizer.texts_to_sequences([text])
    return_dict.update({'Text':text})

    #   Calculate length of the tweet
    length = len(text.split())
    #   Calculate Automated Readability Index of the Tweet
    ari = textstat.automated_readability_index(text)
    #   Calculate average character in words for the Tweet
    words = text.split()
    char = float(sum(len(word) for word in words) / len(words))

    return_dict.update(
        {'Length_tweet':str(length),
         'Ari_tweet':str(ari),
         'Char_tweet':str(char)}
    ) 
    
    model = 'word2seq_cnn'
    x_test = keras_seq.pad_sequences(list_tokenized_test, 
                                        maxlen=INPUT_SIZE[model],
                                        padding='post')
    x_test = x_test.astype(np.int64)

    ## Predict using the loaded model
    emotion = 0
    
    afraid_probability = pred_models[model].predict_proba(x_test)[0][0]
    anger_probability = pred_models[model].predict_proba(x_test)[0][1]
    bored_probability = pred_models[model].predict_proba(x_test)[0][2]
    excited_probability = pred_models[model].predict_proba(x_test)[0][3]
    happy_probability = pred_models[model].predict_proba(x_test)[0][4]
    relax_probability = pred_models[model].predict_proba(x_test)[0][5]
    sad_probability = pred_models[model].predict_proba(x_test)[0][6]
    worry_probability = pred_models[model].predict_proba(x_test)[0][7]


    arr = [afraid_probability, anger_probability, bored_probability, excited_probability, happy_probability, relax_probability, sad_probability, worry_probability]
    max = arr[0]
    

    for i in range(0, len(arr)):
        if arr[i] > max:
            max = arr[i]
    
    if max == afraid_probability:
        emotion = 0

    if max == anger_probability:
        emotion = 1
    
    if max == bored_probability:
        emotion = 2
    
    if max == excited_probability:
        emotion = 3
    
    if max == happy_probability:
        emotion = 4
    
    if max == relax_probability:
        emotion = 5
    
    if max == sad_probability:
        emotion = 6
    
    if max == worry_probability:
        emotion = 7

    # save_to_db(model, text, emotion, anger_probability, fear_probability, joy_probability, love_probability, sadness_probability, surprise_probability)
    
    return_dict.update({table_name[model]: #word2seq_cnn, word2vec_cnn, ...
        {
            retName[0]:str(emotion),
            retName[1]:str(max),
            retName[2]:str(afraid_probability), 
            retName[3]:str(anger_probability),
            retName[4]:str(bored_probability),
            retName[5]:str(excited_probability),
            retName[6]:str(happy_probability),
            retName[7]:str(relax_probability),
            retName[8]:str(sad_probability),
            retName[9]:str(worry_probability)
        }
    })
    
    return(return_dict)

def analyse(data):
    joblib_model = xgb.Booster({'nthread':4})
    
    joblib_model.load_model('./EIM_Model/xgboost_19.pkl')
    
    return_dict = {}
    
    print (request.json, flush=True)
    print(data,flush=True)
    feature = [float(i) for i in data.split(',')]

    return_dict = {}

    values = pd.DataFrame( [feature],
                            columns=header,
                            dtype=float,
                            index=['input']
                            )

    input_variable = xgb.DMatrix(values)

    afraid_probability = joblib_model.predict(input_variable)[0][0]
    anger_probability = joblib_model.predict(input_variable)[0][1]
    bored_probability = joblib_model.predict(input_variable)[0][2]
    excited_probability = joblib_model.predict(input_variable)[0][3]
    happy_probability = joblib_model.predict(input_variable)[0][4]
    relax_probability = joblib_model.predict(input_variable)[0][5]
    sad_probability = joblib_model.predict(input_variable)[0][6]


    return_dict.update({ #word2seq_cnn, word2vec_cnn, ...
        retName_v2[0]:str(afraid_probability), 
        retName_v2[1]:str(anger_probability),
        retName_v2[2]:str(bored_probability),
        retName_v2[3]:str(excited_probability),
        retName_v2[4]:str(happy_probability),
        retName_v2[5]:str(relax_probability),
        retName_v2[6]:str(sad_probability)
    })

    print (return_dict,flush=True)
    return (return_dict)

if __name__ == '__main__':
    app.run(host='localhost', port=5000)