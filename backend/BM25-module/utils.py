# utils.py
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

STOP_WORDS = set(stopwords.words('english'))

def preprocess_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    tokens = word_tokenize(text)
    tokens = [word for word in tokens if word not in STOP_WORDS and len(word) > 2]
    return tokens