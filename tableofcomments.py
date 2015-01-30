"""
Plugin to create a quick panel lookup that lets you jump between comment
titles
"""

import os
import imp
import sys
import sublime
import sublime_plugin
import re


#
# Plugin command
#
class table_of_comments_command(sublime_plugin.TextCommand):

    def run(self, edit, move=None):
        if move is not None:
            return self.traverse_comments(edit, move)
        else:
            view = self.view
            toc = TableOfComments(view, edit)
            toc.create_toc()
            titles = toc.get_comment_titles('string')
            self.window = sublime.active_window()
            if sys.version_info < (3, 0):
                self.window.show_quick_panel(titles, toc.on_list_selected_done)
            else:
                self.window.show_quick_panel(  # Pass on_highlighted callback
                    titles, toc.on_list_selected_done, False, 0,
                    toc.on_list_selected_done)

    # Allows moving up and down through comments
    def traverse_comments(self, edit, move):
        view = self.view
        toc = TableOfComments(view, edit)
        titles = toc.get_comment_titles()
        sel = view.sel()
        if len(sel) == 1:
            current_line_no, col_no = view.rowcol(sel[0].b)
            for x in range(len(titles)):
                item = titles[x]
                if move == 'up':  # moving up
                    if item['line'] < current_line_no:
                        if x+1 < len(titles):
                            if titles[x+1]['line'] >= current_line_no:
                                return toc.on_list_selected_done(x)
                        else:
                            return self.on_list_selected_done(x)
                else:  # moving down
                    if item['line'] > current_line_no:
                        return toc.on_list_selected_done(x)


#
# Plugin class
#
class TableOfComments:

    def __init__(self, view, edit):
        self.view = view
        self.edit = edit

#
# Table TOC tag
#

    def get_toc_region(self, view):
        title = get_setting('toc_title', str)
        pattern = r'\/\*(\s|\*)*'+title+r'[^\/]*\/'
        matches = view.find_all(pattern)
        for region in (matches):
            if self.is_scope_or_comment(view, region):
                return region
        return None

    def create_toc(self):
        view = self.view
        edit = self.edit
        region = self.get_toc_region(view)
        if region:
            toc = self.compile_toc(view)
            existing = view.substr(region)
            if existing != toc:
                view.replace(edit, region, toc)

    def compile_toc(self, view):
        titles = self.get_comment_titles('string')
        title = get_setting('toc_title', str)
        start = get_setting('toc_start', str)
        line = get_setting('toc_line', str)
        end = get_setting('toc_end', str)
        front = "\n" + line
        output = start + front + title + front.rstrip()
        for title in titles:
            comment_level = title.count('-') + 1
            try:
                level = int(get_setting('toc_level', int))
                if level >= comment_level:
                    output += front + title
            except TypeError:
                output += front + title
        output += "\n"+end
        return output

    # Jump list quick menu selected
    def on_list_selected_done(self, picked):
        if picked == -1:
            return
        titles = self.get_comment_titles()
        row = titles[picked]['line']
        point = self.view.text_point(row, 0)
        line_region = self.view.line(point)
        self.view.sel().clear()
        self.view.sel().add(line_region)
        self.view.show_at_center(line_region.b)

    # Core parse function (returned as dict or list)
    def get_comment_titles(self, format='dict', test=None):
        view = self.view
        level_char = get_setting('level_char', str)
        comment_chars = get_setting('comment_chars', str)
        comment_chars = list(comment_chars)
        comment = 'DIV'.join(comment_chars)
        start = r'\s|'+re.escape(comment).replace('DIV', '|')
        # Allows unlimited number of comment title depths - thanks @MalcolmK!
        pattern = r'^('+start+')*?('+format_pattern(level_char)+'+)\s*?' + \
            r'(\w|\s|[-.,;:\'"|{}<?\/\\\\*@#~!$%^=\(\)\[\]])+('+start+')*?$'
        matches = view.find_all(pattern)
        results = []
        toc_title = get_setting('toc_title', str)

        for match in matches:
            bits = view.lines(match)  # go through each line
            for region in bits:
                # Ensure it's comment or source
                if not self.is_scope_or_comment(view, region):
                    continue
                # Ensure not in toc region already
                if self.is_in_toc_region(view, region):
                    continue
                line = view.substr(region)
                if level_char in line:
                    # Format the line as a label
                    line = line.replace('/*', '').replace('*/', '')
                    for char in comment_chars:
                        if char != level_char:
                            line = line.replace(char, '')

                    # Replace level char with toc char
                    line = self.replace_level_chars(line)

                    # Get the position
                    if line != '' and line != toc_title:
                        line_no, col_no = view.rowcol(region.b)
                        if format == 'dict':
                            results.append({'label': line, 'line': line_no})
                        else:
                            results.append(line)
        return results

    def is_in_toc_region(self, view, region):
        toc_region = self.get_toc_region(view)
        if toc_region:
            if region.a > toc_region.a and region.a < toc_region.b:
                return True
        return False

    # Only find titles within genuine comments
    # This will no doubt need to be improved over time for various syntaxes
    # ('string.quoted' makes python """ comments """ not trigger)
    def is_scope_or_comment(self, view, region):
        scope = view.scope_name(region.a)
        comments_scope = ['comment']
        disallow = ['string.quoted']
        for each in comments_scope:
            if scope.find(each) < 0:
                return False
        for each in disallow:
            if scope.find(each) > 0:
                return False
        return True

    def replace_level_chars(self, line):
        level_char = get_setting('level_char', str)
        toc_char = get_setting('toc_char', str)
        line = line.replace(level_char+' ', ' ')
        line = line.replace(level_char, toc_char).strip()
        return line


#
# Helpers
#

def format_pattern(pattern):
    pattern = re.escape(pattern)
    pattern = pattern.replace('\>', '>')
    return pattern


def get_setting(name, typeof=str):
    settings = sublime.load_settings('tableofcomments.sublime-settings')
    setting = settings.get(name)
    if setting:
        if typeof == str:
            return setting
        if typeof == bool:
            return setting is True
        elif typeof == int:
            return int(settings.get(name, 500))
    else:
        if typeof == str:
            return ''
        else:
            return None


#
# Testing infrastructure
#

if sys.version_info < (3, 0):
    import tests
else:
    from . import tests


class table_of_comments_run_tests_command(sublime_plugin.TextCommand):
    def run(self, edit):
        reload_test_bootstrap()
        tests.run(self.view, edit)


# For developing, reload tests.* which in turn reloads it's sub packages
basedir = os.getcwd()
def reload_test_bootstrap():
    os.chdir(basedir)
    path = 'tests'
    if sys.version_info < (3, 0):
        __import__(path)
        sys.modules[path] = reload(sys.modules[path])
    else:
        imp.reload(eval(path))
