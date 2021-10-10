import pandas as pd
import numpy as np
import re
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.options import Options

from bs4 import BeautifulSoup

from fake_useragent import UserAgent
import undetected_chromedriver as uc

'''
This is a code sample of a web scraper I wrote for as a research assistant under Ben Iverson. It's purpose is to gather 
addresses and ages of individuals given their names and home state. The data gathered with this code was used in the paper
"Explaining Racial Disparities in Personal Bankruptcy Outcomes" to impute the race of judges and trustees in our dataset.
'''

#Remove the middle name of the individual
def remove_middle_name(name):
    names = name.split()
    if len(names) > 1:
        return names[0] + " " + names[-1]
    
#Convert middle name to single character middle name
def strip_middle_name(name):
    names = name.split()
    
    if len(names) < 3:
        return name
    
    middle = names[1]
    middle_initial = middle[0]
    return names[0] + " " + middle_initial + " " + names[-1]

#Check two names and return the match type
def check_two_names(name1, name2):
#Match types
#exact match = 1
#we have a single letter middle and when we strip white pages middle they match = 2
#white pages has a single middle and when we strip our middle they match = 3
#white pages has no middle that matches us with middle removed = 4
#we do not have a middle but when we strip white pages we get a match = 5

    #Clean the names
    name1 = name1.lower().rstrip().lstrip()
    name2 = name2.lower().rstrip().lstrip()
    name1 = re.sub('[^a-zA-Z ]', '', name1)
    name2 = re.sub('[^a-zA-Z ]', '', name2)
    
    #Control for suffix
    if re.findall('(i{2,3}|iv)$', name1) and re.findall('(i{2,3}|iv)$', name2):
        name1 = name1.rsplit(' ', 1)[0]
        name2 = name2.rsplit(' ', 1)[0]
        
    name1 = name1.replace('jr', '')
    name2 = name2.replace('jr', '')
    name1 = name1.replace('sr', '')
    name2 = name2.replace('sr', '')
    
    #Direct match
    if name1 == name2:
        return 1
    
    #If name1 has middle name, remove and compare
    if len(name1.split()) > 2:
        if name2 == remove_middle_name(name1):
            return 4
        elif name2 == strip_middle_name(name1):
            return 2
        elif name1 == strip_middle_name(name2):
            return 3
        
    #If name1 does not have middle name, remove from name2 and compare
    if remove_middle_name(name2) == name1:
        return 5
    
    else:
        return None

#Parses the html on a persons page to get the persons address
def get_address(html):
    soup = BeautifulSoup(html, "html.parser")
    address_div = soup.find_all("div", {"class":"px-5 py-7 info-card pearl d-flex td-n card flat"})
    if address_div:
        address = address_div[0].text.replace("Map","").replace("\n", "").rstrip().lstrip()
        address = ' '.join(address.split())
    else:
        address = 'Not available'
    return address

#Parses through the person page html to get the needed information
def get_info_from_box(html, state):
    soup = BeautifulSoup(html, "html.parser")
   
    #Find their age
    age_div = soup.find_all("div", {"class":"_2MbI subtitle-1"})
    if age_div:
        age = age_div[0].text.split()[1]
    else:
        age = '--'
    
    #Find their current address
    city_div = soup.find_all("div", {"class":"body-1 ash--text"})
    if city_div:
        current_residence = city_div[0].text.split()
    else:
        current_residence = []
    
    for element in city_div:
        element.extract()
        
    #Get their listed name
    name_div = soup.find_all("div", {"class":"_1mHN display-1"})
    if name_div:
        name = ' '.join(name_div[0].text.split())
    else:
        name = ''
    
    #See where else they've lived
    other_locations_div = soup.find_all("div", {"class": "hide-scrollbar body-2 _3n3z"})
    other_residence = []
    if other_locations_div:
        for span in other_locations_div[0].span:
             other_residence = other_residence + span.split()
                
    #Get their 'may go by' names
    may_also_go_by_div = soup.find_all("div", {"class": "hide-scrollbar body-2 _3FSm"})
    other_names = []
    if may_also_go_by_div:
        go_by_names = may_also_go_by_div[0].find_all('span')
        for span in go_by_names:
            other_names.append(span.text.lower().rstrip().lstrip())
    
    #Combind their current and previous addresses
    residence_history = current_residence + other_residence
    
    #If they have an address in the state we know them by return the gathered info, otherwise its not a match
    if state in residence_history:
        return name, age, other_names
    else:
        return " ", " ", other_names
    
#Given a name and state this function looks up the person on whitepages and returns a list of matches containing the whitepages name, address, url, age, number of results, and match type
def scrape_individual_info(name, state):
    
    options = webdriver.ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--log-level=OFF')
    
    ua = UserAgent()
    user_agent = ua.random
    options.add_argument(f'user-agent={user_agent}')
    
    driver = webdriver.Chrome(options=options)
    
    
    #Generate url
    comp = ''
    for component in name.split():
        comp = comp + component + '%20'
    #Remove final %20
    comp = comp[:-3]
    
    url = 'https://www.whitepages.com/name/' + str(name).replace(' ', '-') + '/' + str(state) + '?fs=1&searchedName=' + str(comp) + '&searchedLocation=' + str(state)
    
    #Sleep inorder to avoid over pining the site, want to be good citizens
    time.sleep(5)
    driver.get(url)
    time.sleep(5)
    
    matches = []
    
    #Find number of results
    num_records = driver.find_elements_by_class_name('_1CLp')
    if num_records:
        num_records = [int(i) for i in num_records[0].text.split() if i.isdigit()]
        if num_records:
            num_records = num_records[0]
        else:
            num_records = 1
    else:
        num_records = 0

          
    #Get all search results
    results = driver.find_elements_by_class_name("_2mGd")
    
    #Check each search result to see if its a plausible match
    i = 0
    for box in results2:
        suggested_name, age, other_names = get_info_from_box(box.get_attribute('innerHTML'), state)
        match_type = check_two_names(name, suggested_name)
        
        #If its a plausible match then we grab their information
        if match_type:

            person_url = box.get_attribute('href')

            #Open tab
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[1])
            driver.get(person_url)
            time.sleep(5)
            person_page_html = driver.page_source
            #Close tab
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

            address = get_address(person_page_html)

            matches.append({'whitepages_name': suggested_name, 'age': age, 'address': address, 'url': person_url, 'num_records': num_records, 'match_number':i, 'match_type': match_type, 'alt_name': False})
            i = i+1
        
        #Check their listed 'may go by' names
        for other_name in other_names:
            match_type = check_two_names(name, other_name)
            if match_type:
                person_url = box.get_attribute('href')

                #Open tab
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(person_url)
                time.sleep(5)
                person_page_html = driver.page_source
                #Close tab
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                address = get_address(person_page_html)

                matches.append({'whitepages_name': suggested_name, 'age': age, 'address': address, 'url': person_url, 'num_records': num_records, 'match_number':i, 'match_type': match_type, 'alt_name': True})
                i = i+1
    
    driver.close()
    return matches



    
