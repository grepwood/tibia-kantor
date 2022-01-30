#!/usr/bin/env python3

import sys
import requests
from bs4 import BeautifulSoup
import re
import json
import pdb
from xvfbwrapper import Xvfb
from selenium import webdriver

class browser_engine(object):
	def __init__(self):
		self.profile = ""
		self.options = ""
		self.driver = ""
		self.xvfb = Xvfb(width=1920, height=1080)
		self.xvfb.start()
		self.profile = webdriver.FirefoxProfile()
		self.options = webdriver.FirefoxOptions()
		self.profile.set_preference("intl.accept_languages", "pl")
		self.options.headless = False
		self.profile.update_preferences()
		self.driver = webdriver.Firefox(self.profile, options=self.options)
		self.user_agent = self.driver.execute_script("return navigator.userAgent;")

	def quit(self):
		self.driver.quit()
		self.xvfb.stop()

	def wait_for_document_to_finish_loading(self):
		while self.driver.execute_script("return document.readyState;") != "complete": next

def convert_to_json(html_tag):
	stringified_tag = str(html_tag)
	without_tag_ending = re.sub('</script>$', '', stringified_tag)
	fixed_quotes = re.sub('\\\\"', '"', re.sub('^.*">', '', without_tag_ending))
	fixed_quotes2 = re.sub('}","', '},"', fixed_quotes)
	fixed_quotes3 = re.sub('}"}', '}}', fixed_quotes2)
	plaintext_json = re.sub('":"{"', '":{"', re.sub('^.*">', '', fixed_quotes3))
	byte_obj = bytes(re.sub('\\\\\\\\u', '\\\\u', plaintext_json), 'utf-8')
	return json.loads(byte_obj.decode('unicode-escape'))

def get_tibia_cc_prices(server, browser):
	url = 'https://allegro.pl/listing?string=' + server + ' tibia cc'
	json_nonce = ''
	browser.driver.get(url)
	browser.wait_for_document_to_finish_loading()
	while json_nonce == '':
		soup = BeautifulSoup(browser.driver.page_source, "html.parser")
		temporary_storage = soup.find('link', attrs={'rel': 'preload'})
		if temporary_storage is None:
			pdb.set_trace()
			print('Need to restart browser')
			browser.quit()
			browser = browser_engine()
			browser.driver.get(url)
			browser.wait_for_document_to_finish_loading()
		else:
			json_nonce = temporary_storage.attrs['nonce']
	data_serialize_box_id = soup.find('div', attrs={'data-box-name': 'items-v3'}).attrs['data-box-id']
	tag_containing_json = soup.find('script', attrs={'nonce': json_nonce, 'type': 'application/json', 'data-serialize-box-id': data_serialize_box_id})
	json_dict = convert_to_json(tag_containing_json)
	actual_offers = []
	for possible_offer in json_dict['__listing_StoreState']['items']['elements']:
		if possible_offer['type'] != 'label':
			actual_offers.append(possible_offer)
	result = []
	for offer in actual_offers:
		gp = convert_tibian_cash_to_plain_gp(offer['title']['text'], offer['url'], browser)
		zloty = float(offer['price']['normal']['amount'])
		zloty_per_kk = zloty / ( gp / 1000000 )
		result.append({'price': zloty, 'gp': gp, 'rate': zloty_per_kk, 'name': offer['title']['text'], 'url': offer['url']})
	return result

def try_to_get_from_offer_url(url, browser):
	result = 0
	kk_regex = re.compile('[0-9]+k+', re.IGNORECASE)
	cc_regex = re.compile('[0-9]+cc', re.IGNORECASE)
	browser.driver.get(url)
	browser.wait_for_document_to_finish_loading()
	soup = BeautifulSoup(browser.driver.page_source, "html.parser")
	found = False
	bag = []
	for line in soup.find('div', attrs={'class': 'offer-page__description'}).findChildren('p'):
		bag = kk_regex.findall(line.text)
		if len(bag) != 0:
			k_amount = len(re.sub('^[0-9]+', '', bag[0]))
			result = int(re.sub('k+$', '', bag[0], flags=re.IGNORECASE)) * 1000 ** k_amount
			found = True
			break
		bag = cc_regex.findall(line.text)
		if len(bag) != 0:
			result = int(re.sub('cc$', '', bag[0], flags=re.IGNORECASE)) * 10000
			found = True
			break
	return [found, result]

def convert_tibian_cash_to_plain_gp(offer_name, offer_url, browser):
	result = 0
	kk_regex = re.compile('[0-9]+k+', re.IGNORECASE)
	cc_regex = re.compile('[0-9]+cc', re.IGNORECASE)
	cc_regex_with_space = re.compile('[0-9]+ cc', re.IGNORECASE)
	just_in_case = []
	try:
		while True:
			bag = kk_regex.findall(offer_name)
			if len(bag) != 0:
				k_amount = len(re.sub('^[0-9]+', '', bag[0]))
				result = int(re.sub('k+$', '', bag[0], flags=re.IGNORECASE)) * 1000 ** k_amount
				break
			bag = cc_regex.findall(offer_name)
			if len(bag) != 0:
				result = int(re.sub('cc$', '', bag[0], flags=re.IGNORECASE)) * 10000
				break
			bag = cc_regex_with_space.findall(offer_name)
			if len(bag) != 0:
				result = int(re.sub(' cc$', '', bag[0], flags=re.IGNORECASE)) * 10000
				break
			just_in_case = try_to_get_from_offer_url(offer_url, browser)
			if just_in_case[0]:
				result = just_in_case[1]
				break
			raise ValueError('Cannot determine offered gp amount.')
	except ValueError:
		pdb.set_trace()
	return result

def find_best_offers_index(offers):
	count = 0
	amount = len(offers)
	if amount == 1:
		return 0
	result = 0
	minimum = offers[0]['rate']
	array = []
	while count < amount:
		if offers[count]['rate'] < minimum:
			minimum = offers[count]['rate']
			result = count
		count += 1
	count = 0
	while count < amount:
		if offers[count]['rate'] == minimum:
			array.append(count)
		count += 1
	return array

def find_table_pointer(soup):
	result = 0
	found = False
	for item in soup.findAll('table', attrs={'class': 'TableContent'}):
		if item.find('td').text == 'Regular Worlds':
			found = True
			break
		result += 1
	assert found == True
	return result+1

def parse_worlds_from_page(url):
	session = requests
	text = session.get(url).text
	soup = BeautifulSoup(text, "html.parser")
	table_pointer = find_table_pointer(soup)
	bag = soup.findAll('table', attrs={'class': 'TableContent'})[table_pointer].findChildren('tr')
	result = []
	for item in bag:
		if item.attrs['class'] != ['LabelH']:
			result.append(item.find('a').text)
	return result

	def __cli_select_episode(self):
		while True:
			print('Select 0 to quit safely')
			while True:
				input_episode = input("Enter episode number (1-"+str(self.episode_count)+"): ")
				if re.match('^[0-9]+$', input_episode):
					break
				else:
					print('Numbers only, buddy')
			episode_number = int(input_episode)
			if episode_number > self.episode_count or episode_number < 1:
				if episode_number == 0:
					return -1
				print('Episode number outside of given range')
			else:
				return episode_number - 1

def choose_server():
	worlds = parse_worlds_from_page('https://www.tibia.com/community/?subtopic=worlds')
	amount_worlds = len(worlds)
	print('Available options:')
	counter = 0
	print('0 - close program')
	for item in worlds:
		counter += 1
		print(str(counter) + ' - ' + item)
	result = -1
	while True:
		input_world = input('Select [0-' + str(amount_worlds) + ']: ')
		if re.match('^[0-9]+$', input_world):
			result = int(input_world)
			if result > -1 and result < amount_worlds:
				result = int(input_world)
				break
			else:
				print('Input out of bounds')
		else:
			print('Not a non-negative integer')
	if result == 0:
		sys.exit(0)
	return worlds[result-1]

tibia_server = choose_server()
print('Allegro cc offers for Tibia server: ' + tibia_server)
browser = browser_engine()
offer = get_tibia_cc_prices(tibia_server, browser)
browser.quit()
best_offers_indices = find_best_offers_index(offer)
for best in best_offers_indices:
	print('Rate: ' + ("%0.2f" % offer[best]['rate']) + ' from ' + offer[best]['url'])

print('')
print('Other, worse offers:')
count = 0
while count < len(offer):
	if not count in best_offers_indices:
		print('Rate: ' + ("%0.2f" % offer[count]['rate']) + ' from ' + offer[count]['url'])
	count += 1
