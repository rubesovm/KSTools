#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys, os
import requests 
from pprint import pprint
import utils

# And pass locale in constructor
SERVER_URL = 'https://www.khanacademy.org'
DEFAULT_API_RESOURCE = '/api/v1/'
# Version 2 is not documented, here used only for topic tree
# But apparently does not even fetch the whole tree, so new code will be needed
#DEFAULT_API_RESOURCE = '/api/v2/'
API2 = '/api/v2/'

kapi_headers = {
   'Content-Type': 'application/json',
   'format': 'json'
}

_EXIT_ON_HTTP_ERROR = True


class KhanAPI:

    def __init__(self, locale):
        if locale == 'en':
            self.server_url = 'https://www.khanacademy.org'
        else:
            self.server_url = 'https://' + locale + '.khanacademy.org'
        self.default_api_resource = '/api/v1/'
        self.session = requests.Session()
        self.headers = {
            'Content-Type': 'application/json',
            'format': 'json'
        }

    def _get_url(self, url, body = {}):
        try:
            r = self.session.get(url, params = body, headers = self.headers)
            r.raise_for_status()
            return r.json()

        except requests.HTTPError as e:
            utils.eprint('HTTP error for URL: ', url)
            utils.eprint(e)
            try:
                utils.eprint(r.json())
            except:
                # Catch exception when r.json is empty
                pass
            if _EXIT_ON_HTTP_ERROR:
                sys.exit(1)
            else:
                return {}

    def download_video(self, YTID):
        # Searching by YTID is deprecated but seems to work,
        # even searching by translated_youtube_id
        # Instead_ we should be calling this by readable_id
        url = self.server_url + self.default_api_resource + 'videos/'  + YTID
        json_response = self._get_url(url)
        return json_response

    def download_article(self, article_id):
        url = self.server_url + self.default_api_resource + 'articles/'  + article_id
        json_response = self._get_url(url)
        return json_response

    # This is not tested
    def download_topic(topic_title, kind):
        url = self.server_url + self.default_api_resource + 'topic/'  + topic_title
        if kind == 'video' or kind == 'exercise':
            url += '/' + kind + 's'
        json_response = self._get_url(url)
        return json_response


    # TODO: Convert to V2 API
    # It seems that the kind argument does not work?
    # EDIT: It seems that the V2 approach will not work here...
    def download_topic_tree(self, content_type):
        """Content type can be 'video', 'exercise', 'topic'"""
        #url = self.server_url + API2 + 'topics/topictree'
        url = self.server_url + self.default_api_resource + 'topictree'
        body = {
            "kind": content_type
        }
        json_response = self._get_url(url, body)
        return json_response


# We want this to be decoupled from KhanAPI object to allow for off-line use
class KhanContentTree():

    def __init__(self, locale, content_type):
        self.content_tree = None
        self.content_type = content_type
        self.file_name = "khan_tree_" + locale + '_' + self.content_type + "_bin.pkl"

    def save(self, tree):
        utils.save_obj_bin(tree, self.file_name)
        self.content_tree = tree

    def load(self):
        if not os.path.isfile(self.file_name):
            print("ERROR: Could not load content tree from file '%s'" % (self.file_name))
            # TODO: Try to download Khan Tree here
            sys.exit(1)
        self.content_tree = utils.load_obj_bin(self.file_name)

    def get(self):
        if self.content_tree is None:
            self.load()
        return self.content_tree

    # This is a bit of a weird function, maybe we should just get rid of the unique bit
    # and handle uniqueness outside of this function?
    def get_unique_content_data(self, ids, out, keys, tree = None):
        if type(ids) is not set or type(out) is not list:
            print("ERROR: Invalid argument to get_unique_content_data!")
            sys.exit(1)

        if tree is None:
            tree = self.content_tree

        if 'kind' not in tree.keys():
            print("ERROR: Could not find 'kind' attribute among:" )
            print(tree.keys())
            sys.exit(1)

        if tree["kind"].lower() == self.content_type and tree['id'] not in ids:
            ids.add(tree['id'])
            data = {}
            for k in keys:
                data[k] = tree[k]
            out.append(data)

        elif tree["kind"] == "Topic":
            # This can happen if Topic includes only Exercises or Articles
            if len(tree["children"]) <= 0:
                return
            for t in tree["children"]:
                self.get_unique_content_data(ids, out, keys, t)


    def get_topics(self, topics, tree = None, render_type = 'all'):
        if tree is None:
            if self.content_tree is None:
                self.load()
            tree = self.content_tree
        if tree["kind"] == "Topic":
            if render_type == 'all' or tree['render_type'] == render_type:
                topics.append(tree)
            for child in tree["children"]:
                self.get_topics(topics, child, render_type)

    def get_lessons(self, lessons, tree = None):
        return self.get_topics(lessons, tree, 'Tutorial')

    def get_units(self, units, tree = None):
        return self.get_topics(units, tree, 'Topic')

    def get_domains(self, domains, tree = None):
        return self.get_topics(domains, tree, 'Domain')

    def get_courses(self, courses, tree = None):
        return self.get_topics(courses, tree, 'Subject')

    def find_video(self, attr, attr_name, tree = None):
        if tree is None:
            if self.content_tree is None:
                self.load()
            tree = self.content_tree

        if "children" not in tree.keys() or len(tree['children']) == 0:
            return None
        # Breadth first search
        for c in tree['children']:
            if c['kind'] == 'Video' and c[attr_name] == attr:
                return c
            result = self.find_video(attr, attr_name, c)
            if result is not None:
                return result
        return None


# TODO: Move functions below into classes above
def kapi_tree_print_full(tree, out_list):
    delim = ';'
    if len(out_list) == 0:
        #out_list.append("SUBJECT"+delim+"TOPIC"+delim+"TUTORIAL"+delim+"TITLE\n")
        out_list.append("\n")
    # Attempting to make Full domain listing work
    #if tree["kind"] == "Topic" and tree["render_type"] == 'Subject':
    #   out_list.append("\n")
    if tree["kind"] == "Topic":

        if len(tree["children"]) <= 0:
            # This can happen if Topic includes only Exercises or Articles
            # Articles seems to be topics as well
           out_list.append('\n')
           return
        for c in tree["children"]:
            if c['kind'] == "Topic":
                title = c['title']
                if title.split()[0] != "Skill":
                    #out_list.append(title+'\t'+c['description']+'\n')
                    # Dirty hack to align columns
                    if c['render_type'] == 'Tutorial' and out_list[-1][-1] == '\n':
                        out_list.append(delim+title+delim)
                    else:
                        out_list.append(title+delim)
            kapi_tree_print_full(c, out_list)

    else:

        title = tree['title']
        desc = tree['description']
        if desc is None:
            desc = " "
        else:
            desc = desc.expandtabs(0).replace('\n',' ')
        ka_url = tree['ka_url']

        if tree["kind"] == "Video":
            ytid = tree["youtube_id"]
            yt_url = 'https://www.youtube.com/timedtext_video?v=' + ytid
            dur = str(tree['duration'])
        else:
            ytid = " "
            yt_url = " "
            dur = " "

        # Dirty hack to make columns aligned
        if out_list[-1][-1] == '\n':
            table_row = delim+delim
        else:
            table_row = ''

        table_row = table_row + title+delim+ka_url

        # For videos, add links to YouTube and video duration
        if tree["content_kind"] == "Video":
            table_row = table_row + delim + ytid + delim + yt_url + delim + dur

        # For exercises, add link to Translation Portal
        if tree["content_kind"] == "Exercise":

            table_row = table_row + delim + create_tp_link(tree['node_slug'])

        table_row = table_row + '\n'

        out_list.append(table_row)

def create_tp_link(node_slug):
    # WARNING: hardcoded cs locale
    TP_URL = 'https://www.khanacademy.org/translations/edit/cs/'
    return TP_URL + node_slug + '/tree/upstream'


def find_ka_topic(tree, title):
    if "children" not in tree.keys() or len(tree['children']) == 0:
        return None
    # Breadth first search
    for c in tree['children']:
        if c['title'] == title or c['slug'] == title:
            return c
        result = find_ka_topic(c, title)
        if result is not None:
           return result
    return None


def find_video_by_youtube_id(tree, ytid):
    if "children" not in tree.keys() or len(tree['children']) == 0:
        return None
    # Breadth first search
    for c in tree['children']:
        if 'youtube_id' in c.keys() and c['youtube_id'] == ytid:
            return c
        result = find_video_by_youtube_id(c, ytid)
        if result is not None:
           return result
    return None


def kapi_tree_get_content_items(tree, content, content_type="all"):
    if tree["kind"] != "Topic":
        #if content_type == "all" or content_type == tree["content_kind"].lower():
        if content_type == "all" or content_type == tree["kind"].lower():
            content.append(tree)
        return

    for c in tree['children']:
        kapi_tree_get_content_items(c, content)

