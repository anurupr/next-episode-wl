__author__ = "Gabriel Melillo<gabriel@melillo.me>"
__version__ = "0.5.7"

import mechanize
from uuid import uuid3, NAMESPACE_OID
from urllib import urlencode
from regexp import regexp_search, Expression
from httplib2 import Http
from httplib import BadStatusLine
from bs4 import BeautifulSoup
from time import time2str, get_offset_time, str2time
from socket import error as socket_error
from cache import TVRageCache


class List(object):
    list = []

    def __init__(self, default=[]):
        self.list = default

    def __getitem__(self, item):
        return self.list[item]

    def __iter__(self):
        for item in self.list:
            yield item

    def __len__(self):
        return len(self.list)

    def __setitem__(self, key, value):
        self.list[key] = value

    def __repr__(self):
        return "<{} List of {} item>".format(self.__class__.__name__, self.__len__())

    def __str__(self):
        return self.__repr__()

    def append(self, value):
        for item in self.list:
            if item == value:
                return False
        self.list.append(value)
        return True


class NextEpisode(List):
    rooturl = "http://next-episode.net"

    def __init__(self, username, password, **kwargs):
        super(List, self).__init__()
        self.browser = mechanize.Browser()
        self.browser.addheaders = [('User-agent', 'Firefox')]
        self.add_show = self.append
        self.today_list = []

        self._cache_dir = '/tmp/.necd'
        self._logghedin = False
        self._username = username
        self._password = password
        self._offset = kwargs.get('offset', 0)

        self._cache = TVRageCache(cachefile=kwargs.get('cachefile', TVRageCache.DEFAULT_CACHE_FILE))

        if kwargs.get('autologin', True):
            self.do_login(
                username=username,
                password=password
            )


        if self._logghedin:
            if kwargs.get('autoupdate', True):
                self.update_list()

    def __repr__(self):
        return "<{} {}@next-episode.net WL: {} Shows>".format(self.__class__.__name__, self._username, self.__len__())

    def do_login(self, username, password):
        self.browser.open(self.rooturl)
        self.browser.select_form(name="login")
        self.browser.form['username'] = username
        self.browser.form['password'] = password
        html = self.browser.submit()
        #html = self.browser.read();
        soup = BeautifulSoup(html)
        tds = soup.findAll("td", attrs = { 'class': 'tdc2'});
        invalidDiv = None
        for td in tds:
            invalidDiv = td.find("div",style="border: 1px solid red;margin-left:20px;padding-left:5px;border-left:2px solid red;padding-top:10px;padding-bottom:10px;");
	
	if invalidDiv != None:
            text = invalidDiv.get_text()
            if "invalid" in text.lower():
                self._logghedin = False
            else:
                self._logghedin = True 
        else:
            self._logghedin = True

        

    def update_list(self):
        if not self._logghedin:
            self.do_login(self._username, self._password)

        html = self.browser.open(self.rooturl+'/user/'+self._username).read()
        soup = BeautifulSoup(html)
        divs = soup.findAll('div',
                            attrs={
                                'class': 'item'
                            })
        self.list = []
        for div in divs:
            spans = div.findAll('span',attrs={'class':'headlinehref'})
            for span in spans:
		link = span.find("a")
                img = link.find("img")
                if link.contents[0] == "V":
                    link.contents[0] = "V (2009)"
                try:
                    self.append({
                        'name': link.get_text(),
                        'uuid': uuid3(NAMESPACE_OID, link.get('href').encode('utf8', 'ignore')).__str__(),
                        'link': self.rooturl+link.get('href').encode('utf8', 'ignore'),
                        'imgurl' : 'http:'+img.get('src')
                    })
                except UnicodeDecodeError:
                    self.append({
                        'name': link.contents[0],
                        'uuid': 'N/A',
                        'link': self.rooturl+link.get('href').encode('utf8', 'ignore'),
                        'imgurl' : 'http://'+img.get('src')
                    })

        print "{} TV Shows in watchlist".format(len(self.list))

    def parse_episode_contents(self,contents,prev=True):
        indexes = {}
        print '\n'
        print contents
        print '\n'
        if prev:
            indexes = {"title" : 5 , "next-episode-date" : 10, "season" : [13,14], "episode" : 17}
        else:
            indexes = {"title" : 5 , "season" : [17,18], "countdown" : 10, "next-episode-date" : 14, "episode" : 21}

        episode = {}
        for key in indexes.keys():
            if type(indexes[key]) is not list:
                html = str(contents[indexes[key]])
                soup = BeautifulSoup(html) 
                episode[key] = soup.get_text().strip()
            else:
                html = ''.join(str(contents[i]) for i in indexes[key])
                soup = BeautifulSoup(html)
                episode[key] = soup.get_text().strip()

        return episode


    def get_episode(self,tvshowurl,prev=False,next=True,get_air_time=False):
        html = self.browser.open(tvshowurl).read()
        soup = BeautifulSoup(html)
        ret = {}

        if prev:
	    # prev episode
            prevEpisode = {}
            prevEpisodeDiv = soup.find('div',id='previous_episode')
            prevEpisode = self.parse_episode_contents(prevEpisodeDiv.contents,prev=True)	
            print prevEpisode
            ret['prev'] = prevEpisode
        
        if next:
            # next episode
            nextEpisodeDiv = soup.find('div',id='next_episode')
            nextEpisode = self.parse_episode_contents(nextEpisodeDiv.contents,prev=False)
            print nextEpisode
            ret['next'] = nextEpisode

        if get_air_time:
            tvshowDiv = soup.find('div',id='middle_section')
            c = tvshowDiv.contents
            html = ''.join(str(c[i]) for i in [7,8,9,10])
            soup = BeautifulSoup(html)
            ret['air-time'] = soup.get_text().strip()+" EDT"

        
        return ret

        	

    def _regexp_tvrage(self, content):
        return {
            'Show ID': regexp_search(Expression.SHOW_ID, content),
            'Show Name': regexp_search(Expression.SHOW_NAME, content),
            'URL': regexp_search(Expression.URL, content),
            'Premiered': regexp_search(Expression.PREMIERED, content),
            'Country': regexp_search(Expression.COUNTRY, content),
            'Status': regexp_search(Expression.STATUS, content),
            'Classification': regexp_search(Expression.CLASSIFICATION, content),
            'Genres': regexp_search(Expression.GENRES, content),
            'Network': regexp_search(Expression.NETWORK, content),
            'Airtime': regexp_search(Expression.AIRTIME, content),
            'Latest Episode': {
                'Number': regexp_search(Expression.LEPISODE, content, number=1),
                'Title': regexp_search(Expression.LEPISODE, content, number=2),
                'Air Date': get_offset_time(
                    regexp_search(Expression.LEPISODE, content, number=3),
                    offset=self._offset
                )
            },
            'Next Episode': {
                'Number': regexp_search(Expression.NEPISODE, content, number=1),
                'Title': regexp_search(Expression.NEPISODE, content, number=2),
                'Air Date': get_offset_time(
                    regexp_search(Expression.NEPISODE, content, number=3),
                    offset=self._offset
                )
            }
        }

    def attach_tvrage_info(self):
        for idx, show in enumerate(self.list):
            h = Http(self._cache_dir)
            url = "http://services.tvrage.com/tools/quickinfo.php?{}".format(
                urlencode({
                    'show': show['Name'][0].__str__(),
                    'exact': 1
                })
            )
            _today = time2str()

            self.list[idx]['TV Rage'] = self._cache.get_cache(self.list[idx]['index'])
            if self.list[idx]['TV Rage'] is None:
                try:
                    resp, content = h.request(url)
                except socket_error:
                    resp, content = ("", "")
                except BadStatusLine:
                    resp, content = ("", "")

                self.list[idx]['TV Rage'] = self._regexp_tvrage(content)
                if self.list[idx]['TV Rage']['Next Episode']['Air Date'] == 'N/A':
                    _expire = str2time(get_offset_time(time2str(), offset=7))
                else:
                    _expire = str2time(self.list[idx]['TV Rage']['Next Episode']['Air Date'])

                self._cache.write_cache(
                    self.list[idx]['index'],
                    self.list[idx]['TV Rage'],
                    _expire
                )

            if _today == self.list[idx]['TV Rage']['Next Episode']['Air Date']:
                self.today_list.append(self.list[idx])
            if _today == self.list[idx]['TV Rage']['Latest Episode']['Air Date']:
                self.today_list.append(self.list[idx])
