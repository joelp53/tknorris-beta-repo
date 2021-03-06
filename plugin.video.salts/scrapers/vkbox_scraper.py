"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import scraper
import urlparse
import xbmcaddon
import xbmc
import zipfile
import StringIO
import json
from salts_lib.db_utils import DB_Connection
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from salts_lib.constants import QUALITIES

BASE_URL = 'http://mobapps.cc'
ZIP_URL = '/data/data_en.zip'
JSON_FILES = {VIDEO_TYPES.MOVIE: 'movies_lite.json', VIDEO_TYPES.TVSHOW: 'tv_lite.json'}
LINKS = {VIDEO_TYPES.MOVIE: '/api/serials/get_movie_data/?id=%s', VIDEO_TYPES.TVSHOW: '/api/serials/es/?id=%s', VIDEO_TYPES.EPISODE: '/api/serials/e/?h=%s&u=%01d&y=%01d'}
STREAM_URL = 'https://vk.com/video_ext.php?oid=%s&id=%s&hash=%s'
VKBOX_AGENT = 'android-async-http/1.4.1 (http://loopj.com/android-async-http)'

class VKBox_Scraper(scraper.Scraper):
    base_url=BASE_URL
    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout=timeout
        self.db_connection = DB_Connection()
        self.base_url = xbmcaddon.Addon().getSetting('%s-base_url' % (self.get_name()))
   
    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.TVSHOW, VIDEO_TYPES.EPISODE, VIDEO_TYPES.MOVIE])
    
    @classmethod
    def get_name(cls):
        return 'VKBox'
    
    def resolve_link(self, link):
        return link
    
    def format_source_label(self, item):
        label='[%s] %s' % (item['quality'], item['host'])
        return label
    
    def get_sources(self, video):
        source_url=self.get_url(video)

        hosters = []
        if source_url:
            params = urlparse.parse_qs(urlparse.urlparse(source_url).query)
            print params
            if video.video_type == VIDEO_TYPES.EPISODE:
                magic_num = int(params['h'][0]) + int(params['u'][0]) + int(params['y'][0])
            else:
                magic_num = int(params['id'][0]) + 537
            
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, user_agent = VKBOX_AGENT, cache_limit=.5)
            if html:
                json_data = json.loads(html)
                
                try: langs = json_data['langs']
                except: langs = json_data
                for lang in langs:
                    if lang['lang']=='en':
                        stream_url = STREAM_URL % (str(int(lang['apple']) + magic_num), str(int(lang['google']) + magic_num), lang['microsoft'])
                        hoster = {'multi-part': False, 'url': stream_url, 'host': 'vk.com', 'class': self, 'quality': QUALITIES.HD, 'views': None, 'rating': None, 'direct': False}
                        hosters.append(hoster)
                        break
                else:
                    log_utils.log('No english language found from vkbox: %s' % (langs), xbmc.LOGWARNING)
            else:
                log_utils.log('No data returned from vkbox: %s' % (url), xbmc.LOGWARNING)
            
        return hosters

    def get_url(self, video):
        return super(VKBox_Scraper, self)._default_get_url(video)
    
    def search(self, video_type, title, year):
        results=[]
        json_data = self.__get_json(video_type)
        norm_title = self._normalize_title(title)
        for item in json_data:
            match_year = item.get('year','')
            if norm_title in self._normalize_title(item['title']) and (not year or not match_year or year == match_year):
                result={'url': LINKS[video_type] % (item['id']), 'title': item['title'], 'year': match_year}
                results.append(result)
        return results
    
    def __get_json(self, video_type):
        url = urlparse.urljoin(self.base_url, ZIP_URL)
        zip_data = self._http_get(url, cache_limit=0)
        if zip_data:
            zip_file = zipfile.ZipFile(StringIO.StringIO(zip_data))
            data = zip_file.read(JSON_FILES[video_type])
            zip_file.close()
            return json.loads(data)
        else:
            return []
        
    def _get_episode_url(self, show_url, video):
        if not self._force_title(video):
            show_id = urlparse.parse_qs(urlparse.urlparse(show_url).query)['id'][0]
            return LINKS[video.video_type] % (show_id, int(video.season), int(video.episode))
    
    def _http_get(self, url, user_agent=None, cache_limit=8):
        return super(VKBox_Scraper, self)._cached_http_get(url, self.base_url, self.timeout, user_agent=user_agent, cache_limit=cache_limit)
