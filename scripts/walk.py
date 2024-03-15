#!/usr/bin/env python3 

import os
import sys 
import json
from abc import abstractmethod 

class Graph(object):

    root = None 

    def __init__(self, *args, **kwargs):
        pass 

    def _find_node(self, name, from_node=None):
        if not from_node and self.root:
            from_node = self.root 
        if not from_node:
            return None 
        if from_node.name == name:
            return from_node 
        found = None 
        for child in from_node.children:
            found = self._find_node(name, child)
            if found: 
                break 
        return found 

    def add_files(self, name, *files):
        '''
        Adds files to node of given name. If no node by this name exists, it is created at becomes root.
        '''

        found_node = self._find_node(name)

        if found_node:
            found_node.add_files(*files)
        else:
            self.root = Node(name, files=files)

    def add_node(self, parent_name, name):
        '''
        Adds a new node with given name to the node with parent_name. If no parent_name node exists, it is created and becomes the root.
        '''

        found_node = self._find_node(parent_name)

        c = Node(name)

        if found_node:
            found_node.add_child(c)
        else:
            self.root = Node(parent_name, children=c)
    
    def walk(self, at_node=None):
        if not at_node:
            at_node = self.root 
        yield at_node 
        for i, child in enumerate(at_node.children, 1):
            yield from self.walk(child)

    def print(self, at_node=None, level=0, is_lasts=[]):
        if not at_node and self.root:
            at_node = self.root 
        if not at_node:
            return 

        # -- if level 0, no prefix 
        # -- levels > 0, the printing of the node should be prefixed with 
        # -- a pipe/break/pipe/leader for the node's parent where the pipes align with the first character of the parent name 
        # -- a pipe aligned to each ancestor whose child is not the last child for that ancestor 
        # -- note that this excludes the node itself (if the node itself is the last child for its ancestor, the parent, we still show the pipe)
        # -- this aligned pipe says "my parent has a subsequent sibling rendered beneath me"
        tabs = '   '
        for is_last in is_lasts:
            tabs += ' ' if is_last else '|'
            tabs += '   '
        
        print(f'{tabs}|\n{tabs}|-- {at_node}')

        for i, child in enumerate(at_node.children, 1):
            if len(is_lasts) == level + 1:
                is_lasts[-1] = i == len(at_node.children)
            elif len(is_lasts) == level: 
                is_lasts.append(i == len(at_node.children))
            else:
                while len(is_lasts) > level:
                    del is_lasts[-1]
            self.print(at_node=child, level=level+1, is_lasts=is_lasts)

class Node(object):
    children = None 
    name = None 
    files = None 

    def __init__(self, *args, **kwargs):
        self.name = args[0]
        self.files = []
        # -- files will always be a tuple if present 
        if 'files' in kwargs:
            self.files = [ File(f) for f in list(kwargs['files']) ]
        self.children = []
        if 'children' in kwargs:
            # -- children may be a tuple but can also be a single value 
            if type(kwargs['children']) == tuple:
                self.children = list(kwargs['children'])
            elif type(kwargs['children']) != list:
                self.children = [kwargs['children']]
            else:
                self.children = kwargs['children']
    
    def add_child(self, child):
        self.children.append(child)
    
    def add_files(self, *files):
        self.files.extend([ File(f) for f in list(files) ])
    
    def __str__(self):
        return f'{self.name} ({len(self.files)})'#: {",".join(self.files)}'

class File(object):

    filename = None 
    meta = None 

    def __init__(self, *args, **kwargs):
        self.filename = args[0]
        self.meta = kwargs

    def __str__(self):
        pass 
    
class PipelineProcessor(object):

    @abstractmethod 
    def process(self, iterable):
        pass 

from src.utils.dates import get_target_date 

class TargetFinder(PipelineProcessor):

    def process(self, iterable):
        for node in iterable():
            print(f'{node.name}')
            for f in node.files:
                filepath = os.path.join(node.name, f.filename)
                print(f'\t{filepath}')
                (target_date, target_atime, target_mtime, new_filename, target_date_assigned_from,) = get_target_date(filepath)
                print(f'\t\ttarget_date={target_date} target_atime={target_atime} target_mtime={target_mtime} new_filename={new_filename} target_date_assigned_from={target_date_assigned_from}')
                f.meta['target_date'] = target_date 

class Pipeline(object):

    _pipeline = None 

    def __init__(self, *args, **kwargs):
        if len(args) > 0 and type(args[0]) in (list, tuple,):
            self._pipeline = args[0]
    
    def run(self, graph):
        for p in self._pipeline:
            p.process(graph.walk)

def run(root):
    graph = Graph()
    for folder, subfolders, files in os.walk(root):
        # print(folder)
        # print(subfolders)
        # print(files)
        # print(f'\n***\n')
        graph.add_files(folder, *files)

        for subfolder in subfolders:
            graph.add_node(folder, os.path.join(folder, subfolder))

    #graph.print()

    p = Pipeline([TargetFinder()])
    p.run(graph)

    '''
    at this point, work with the graph object to process photos
    neat idea, expose functions from the photo-binner library to operate as callbacks in a pipeline
    assemble a pipeline here (outside the graph implementation and independent of the photo-binner library itself)
    and either pass the graph into the pipeline or pass the pipeline into the graph (probably the former)

    '''


if __name__ == "__main__":
    root = sys.argv[1]
    run(root)