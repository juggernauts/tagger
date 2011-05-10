#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 by Alessandro Presta

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE


'''
================================================================================

         tagger.py - module for extracting tags from text documents

                   Copyright (C) 2011 by Alessandro Presta

================================================================================

Dependencies: python2.7, stemming, nltk (optional), tkinter (optional),
              lxml (optional)

$ easy_install stemming

================================================================================

Usage:

>>> import tagger

>>> weights = pickle.load(open('data/dict.pkl', 'rb')) # or your own dictionary

>>> myreader = tagger.Reader() # or your own reader class
>>> mystemmer = tagger.Stemmer() # or your own stemmer class
>>> myrater = tagger.Rater(weights) # or your own... (you got the idea)

>>> mytagger = Tagger(myreader, mystemmer, myrater)

>>> best_3_tags = mytagger(text_string, 3)

================================================================================

Running the module as a script:

$ ./tagger.py <text document(s) to tag>

Example: 
$ ./tagger.py tests/*
Loading dictionary... 
Tags for  tests/bbc1.txt :
['bin laden', 'obama', 'pakistan', 'killed', 'raid']
Tags for  tests/bbc2.txt :
['bristol', 'jo yeates', 'vincent tabak', 'murder', '17 december']
Tags for  tests/bbc3.txt :
['snp', 'party', 'labour', 'election', 'scottish']
Tags for  tests/guardian1.txt :
['bin laden', 'al-qaida', 'pakistan', 'killed', 'statement']
Tags for  tests/guardian2.txt :
['clegg', 'party', 'lib dem', 'coalition', 'tory']
Tags for  tests/post1.txt :
['sony', 'playstation network', 'stolen', 'lawsuit', 'hacker attack']
Tags for  tests/wikipedia1.txt :
['anthropic principle', 'universe', 'carter', 'life', 'observed']
Tags for  tests/wikipedia2.txt :
['beetroot', 'beet', 'betaine', 'vegetable', 'blood pressure']

================================================================================
'''

import collections
import re


class Tag:
    '''
    General class for tags (small units of text)
    '''
    
    def __init__(self, string, stem=None, rating=1.0, proper=False,
                 terminal=False):
        '''
        Arguments:

        string    --    the actual representation of the tag
        stem      --    the internal (usually stemmed) representation;
                        tags with the same stem are regarded as equal
        rating    --    a measure of the relevance in the interval [0,1]
        proper    --    whether the tag is a proper noun
        terminal  --    set to True if the tag is at the end of a phrase
                        (or anyway it cannot be logically merged to the
                        following one)

        Returns: a new Tag object
        '''
            
        self.string  = string
        self.stem = stem or string
        self.rating = rating
        self.score = self.rating
        self.proper = proper
        self.terminal = terminal
        
    def __eq__(self, other):
        return self.stem == other.stem

    def __repr__(self):
        return repr(self.string)

    def __lt__(self, other):
        return self.score > other.score

    def __hash__(self):
        return hash(self.stem)


class MultiTag(Tag):
    '''
    Class for aggregates of tags (usually next to each other in the document)
    '''

    def __init__(self, tail, head=None):
        '''
        Arguments:

        tail    --    the Tag object to add to the first part (head)
        head    --    the (eventually absent) MultiTag to be extended

        Returns: a new MultiTag object
        '''
        
        if not head:
            Tag.__init__(self, tail.string, tail.stem, tail.rating,
                         tail.proper, tail.terminal)
            self.size = 1
        else:
            self.string = ' '.join([head.string, tail.string])
            self.stem = ' '.join([head.stem, tail.stem])
            self.size = head.size + 1

            # two proper nouns make a proper noun
            self.proper = (head.proper and tail.proper)
            self.terminal = tail.terminal

            # the measure for multitags is the geometric mean of its unit subtags
            self.rating = head.rating * tail.rating
            # but proper nouns shouldn't be penalized by stopwords
            if self.proper and self.rating == 0.0:
                self.rating = max(head.rating, tail.rating) ** 2
            self.score = self.rating ** (1.0 / self.size)

        
class Reader:
    '''
    Class for parsing a string of text to obtain tags

    (it just turns the string to lowercase and splits it according to
    whitespaces and punctuation, identifying proper nounds and terminal words;
    different rules and formats could be used, e.g. a good HTML-stripping
    facility would be handy)
    '''

    match_punctuation = re.compile('[\.,;:\?!\(\)\[\]\{\}<>]')
    match_delimiters = re.compile('[\t\n\r\f\v]+')
    match_words = re.compile('[\w\-\'_]+')
    
    def __call__(self, text):
        '''
        Arguments:

        text    --    the string of text to be tagged

        Returns: a list of tags respecting the order in the text
        '''
        
        # deal with unicode apostrophes
        text = text.replace('’', '\'')

        text = self.match_punctuation.sub('\n', text)
        phrases = self.match_delimiters.split(text)

        tags = []

        for p in phrases:
            words = self.match_words.findall(p)
            if len(words) >= 2:
                tags.append(Tag(words[0].lower()))
                if len(words) > 2:
                    for w in words[1:-1]:
                        # capitalized words in the middle of a phrase are always
                        # proper nouns
                        tags.append(Tag(w.lower(), proper=w[0].isupper()))
                tags.append(Tag(words[-1].lower(), proper=words[-1][0].isupper(),
                                terminal=True))
            elif len(words) == 1:
                tags.append(Tag(words[0].lower(), terminal=True))

        return tags

    
class Stemmer:
    '''
    Class for extracting the stem of a word
    
    (by deafault it uses a simple open-source implementation of the Porter
    algorithm; this can be improved a lot, so experimenting with different ones
    is advisable; nltk.stem provides different algorithms for many languages)
    '''

    match_contractions = re.compile('(\w+)\'(m|re|d|ve|s|ll|t)?')

    def __init__(self, stemmer=None):
        '''
        Arguments:

        stemmer    --    an object or module with a 'stem' method (defaults to
                         stemming.porter2)

        Returns: a new Stemmer object
        '''
        
        if not stemmer:
            from stemming import porter2
            stemmer = porter2

        self.stemmer = stemmer
    
    def pre_stem(self, string):
        '''
        Arguments:

        string    --    a string to be treated before passing it to the stemmer

        Returns: the processed string
        '''

        # get rid of contractions and possessive forms
        match = self.match_contractions.match(string)
        if match: return match.group(1)
        else: return string
    
    
    def __call__(self, tag):
        '''
        Arguments:

        tag    --    the tag to be stemmed

        Returns: the stemmed tag
        '''

        string = self.pre_stem(tag.string)
        tag.stem = self.stemmer.stem(string)
        return tag    


class Rater:
    '''
    Class for estimating the relevance of tags

    (the default implementation uses TF-ICF weight and geometric mean for
    multitags, but any other measure will work, provided that it is normalized
    in the interval [0,1]; a quite rudimental heuristic tries to discard
    redundant tags)
    '''

    def __init__(self, weights, multitag_size=3):
        '''
        Arguments:

        weights          --    a dictionary of weights normalized in the
                               interval [0,1]
        multitag_size    --    maximum size of tags formed by multiple unit
                               tags

        Returns: a new Rater object
        '''
        
        self.weights = weights
        self.multitag_size = multitag_size

    def create_multitags(self, tags):
        multitags = []
        
        for i in xrange(len(tags)):
            t = MultiTag(tags[i])
            multitags.append(t)
            for j in xrange(1, self.multitag_size):
                if t.terminal or i + j >= len(tags):
                    break
                else:
                    t = MultiTag(tags[i + j], t)
                    multitags.append(t)

        return multitags
        
    def __call__(self, tags):
        '''
        Arguments:

        tags    --    a list of (preferably stemmed) tags

        Returns: a list of unique (multi)tags sorted by relevance
        '''

        term_count = collections.Counter(tags)
        
        for t in tags:
            t.rating = float(term_count[t]) / len(tags) * \
                self.weights.get(t.stem, 1.0)

        multitags = self.create_multitags(tags)

        term_count = collections.Counter(multitags)
        
        # keep most frequent version of each tag
        clusters = collections.defaultdict(collections.Counter)
        for t in multitags:
            clusters[t][t.string] += 1
        for t in term_count:
            t.string = clusters[t].most_common(1)[0][0]
        
        # purge duplicates and one-character tags
        unique_tags = set(t for t in term_count if len(t.string) > 1)
        # remove redundant tags
        for t, cnt in term_count.iteritems():
            words = t.stem.split()
            for i in xrange(len(words)):
                for j in xrange(1, len(words)):
                    subtag = Tag(' '.join(words[i:i + j]))
                    relative_freq = float(cnt) / term_count[subtag]
                    if ((relative_freq == 1.0 and t.proper) or
                        (relative_freq >= 0.5 and t.score > 0.0)):
                        unique_tags.discard(subtag)
                    else:
                        unique_tags.discard(t)
        
        return sorted(unique_tags)
    
    
class Tagger:
    '''
    Master class for tagging text documents

    (this is a simple interface that should allow convenient experimentation
    by using different classes as building blocks)
    '''

    def __init__(self, reader, stemmer, rater):
        '''
        Arguments:

        reader    --    a callable object with the same interface as Reader
        stemmer   --    a callable object with the same interface as Stemmer
        rater     --    a callable object with the same interface as Rater

        Returns: a new Tagger object
        '''
        
        self.reader = reader
        self.stemmer = stemmer
        self.rater = rater

    def __call__(self, text, tags_number=5):
        '''
        Arguments:

        text           --    the string of text to be tagged
        tags_number    --    number of best tags to be returned

        Returns: a list of (hopefully) relevant tags
        ''' 

        tags = self.reader(text)
        tags = map(self.stemmer, tags)
        tags = self.rater(tags)
        
        return tags[:tags_number]



if __name__ == '__main__':

    import glob
    import pickle
    import sys

    if len(sys.argv) < 2:
        print 'No arguments given, running tests: '
        documents = glob.glob('tests/*')
    else:
        documents = sys.argv[1:]
    
    print 'Loading dictionary... '
    weights = pickle.load(open('data/dict.pkl', 'rb'))
    
    tagger = Tagger(Reader(), Stemmer(), Rater(weights))

    for doc in documents:
        with open(doc, 'r') as file:
            print 'Tags for ', doc, ':'
            print tagger(file.read())
          
