import pandas as pd
import numpy as np
import re
from scipy.sparse import csr_matrix
from math import floor, ceil
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


'''
This is a code sample that I wrote as a research assistant under Ben Iverson. Its purpose was to clean a data set of bankruptcy 
court trustees. One of the issues we faced was that the same trustee would be listed multiple times with different names, for 
example: Jon Snow, Jon C Snow, Jon Clark Snow. There were also misspellings in the data set. This code cleans the names and then 
vectorizes the names and uses cosine similarity to group common names that are likely the same person. The results were used in 
the paper "Explaining Racial Disparities in Personal Bankruptcy Outcomes"
'''

#This function will split names up into lagged components for vectorization
def ngrams(string, n=3):
    string = re.sub(r'[,-./]|\sBD',r'', string)
    ngrams = zip(*[string[i:] for i in range(n)])
    return [''.join(ngram) for ngram in ngrams]

#Load the data
df = pd.read_csv('trustees.csv')

#name_id will be used to group names that are similar and likely the same person
df['name_id'] = 0
df = df.drop_duplicates('trustee_name')
df['district'] = df['district'].str.replace('us_ban_', '').str.replace('us_bap_', '')

#Keep the original trustee name
df['trustee_name_original'] = df['trustee_name']

#Clean the trustee names
df.trustee_name = df.trustee_name.str.replace('[^a-zA-Z ]', '').str.lower()
df['suffix'] = df['trustee_name_original'].apply(lambda x: 'jr' if 'jr' in x else 'sr' if 'sr' in x else re.findall('(i{2,3}|iv)$', x)[0] if re.findall('(i{2,3}|iv)$', x) else '')

#Remove jr sr suffix
df.trustee_name = df.trustee_name.str.replace('jr', '').str.replace('sr', '').str.replace('tr', '')

#remove roman numerals
df['trustee_name'] = df['trustee_name'].apply(lambda x: x.rsplit(' ', 1)[0] if re.findall('(i{2,3}|iv)$', x) else x)

#remove everything after these words
up_to_words = ['ustee', 'sbra', 'liquidating', 'acting', 'chapter']

for word in up_to_words:
    df['trustee_name'] = df['trustee_name'].apply(lambda x: re.search('^.*(?=(' + word +'))', x)[0] if word in x else x)

df.trustee_name = df.trustee_name.str.lstrip('').str.rstrip('')

#Save the name length
df['name_length'] = df.apply(lambda x: len(x.trustee_name.split()), axis=1)

#Data frame for matches
matches = pd.DataFrame(columns=['name1','name2','district', 'score'])

#Keep matching within districts
for district in df['district'].unique():
    names = df[df['district']==district]['trustee_name'].unique()
    #Vectorize the names
    vectorizer = TfidfVectorizer(min_df=1, analyzer=ngrams)
    tf_idf_matrix = vectorizer.fit_transform(names)
    
    #For each names calcualte its cosine similarity with the other names in the district, save the most similar ones as matches
    for name in names:
        query_tfidf = vectorizer.transform([name])
        cosineSimilarities = cosine_similarity(query_tfidf, tf_idf_matrix).flatten()
        indices = [i for i,v in enumerate(cosineSimilarities) if v > 0.75]
        matched_names = [(names[i], cosineSimilarities[i])  for i in indices]
        
        for match in matched_names:
            if name == match[0]:
                continue
            else:
                matches = matches.append({'name1': name, 'name2': match[0], 'district': district, 'score': match[1]}, ignore_index=True)            
                
#Now that we have matches will assign name_ids to group names that are likely the same person
curr_id = 1

#For each match...
for index, row in matches.iterrows():
    name1 = row['name1']
    name2 = row['name2']
    name1_id = df[df['trustee_name'] == name1]['name_id'].values[0]
    name2_id = df[df['trustee_name'] == name2]['name_id'].values[0]
    
    #If the name does not have an id generate new id
    if name1_id == 0:
        name1_id = curr_id
        curr_id = curr_id + 1
        df.loc[(df.trustee_name == name1),'name_id']=name1_id
    #If the second name does not have an id assign it to the match id
    if name2_id == 0:
        df.loc[(df.trustee_name == name2),'name_id']=name1_id
    #If the second name has an id, assign that group to the new id
    else:
        df.loc[(df.name_id == name2_id),'name_id']=name1_id
        

#Give all names with out ids matches
df.loc[(df.name_id == 0),'name_id'] = range(curr_id, curr_id+df[df['name_id'] == 0].shape[0])

#Save the results
df.to_csv('trustees_cleaned.csv')