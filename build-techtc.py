#!/usr/bin/env python
import os
import sys
import pickle
from random import seed, random, choice
from lxml import etree
from optparse import OptionParser

# maximum cache size
cache_size = sys.maxint

class Cache:
    '''Simple cache without replacement. f is the function to cache. s
    is the size of the cache'''
    def __init__(self, f, s):
        self._f = f
        self._d = {}
        self._s = s
        self._calls = 0
        self._failures = 0

    def __call__(self, x):
        self._calls += 1
        if x not in self._d:
            y = self._f(*x)
            if len(self._d) < self._s:
                self._d[x] = y
            self._failures += 1
            return y
        return self._d[x]

    def get_failures(self):
        return self._failures

    def get_calls(self):
        return self._calls

    def get_hits(self):
        return self._calls - self._failures


def ns():
    '''contain the namespace of dmoz xml file (kinda hacky)'''
    return "{http://dmoz.org/rdf/}"


def r():
    return "{http://www.w3.org/TR/RDF/}"


def links(contentFileName, cat):
    '''return the list of links of category cat.'''
    cf = open(contentFileName)
    for _,t in etree.iterparse(cf, tag = ns()+"Topic"):
        # print "t.attrib[r()+\"id\"] =", t.attrib[r()+"id"]
        if cat == t.attrib[r()+"id"]:
            l = [n.attrib[r()+"resource"] for n in t.iter() if "link" in n.tag]
            t.clear()
            return l
        t.clear()
    cf.close()
    print cat,"Not found!"
    return []

clinks = Cache(links, cache_size)

def choiceLinks(contentFileName, cat):
    '''Choose randomly a link belonging to cat. If no link exists it
    returns None'''
    l = clinks((contentFileName, cat))
    if l:
        return choice(l)
    else:
        return None


def collectLinks(contentFileName, cats, n = None):
    '''given a set of categories collect a maximum of n links over the
    categories cats.'''
    l = []
    for cat in cats:
        l += clinks((contentFileName, cat))
        if n and len(l) >= n:
            return l[:n]
    return l


def printLinks(ls):
    i = 0
    for l in ls:
        i += 1
        print i, l

def collectLinksBFS(cat, options):
    '''collects up to n links in BFS order from category cat.'''
    cats = [cat]
    l = []
    s = len(l)
    n = options.L
    while s < n and len(cats) > 0:
        l += collectLinks(options.c, cats, n - s)
        s = len(l)
        if s < n:
            cats = sum([csubtopics((options.s, cat,
                                    tuple(options.subtopic_tags)))
                        for cat in cats], [])
        else:
            printLinks(l[:n])
            return l[:n]
    printLinks(l)
    return l


def choiceCollectLinks(cat, options, m = -1):
    '''randomly choose a set of links belonging to a category (or its
    subtopics). If after m attempts the number of links n hasn't
    been reached (considering that duplicated links are ignored) then
    it returns the empty set. If m is negative then there is no limit
    in the number of attempts (which can lead to infinit loop). p is
    the probability to dig deeper in the hierarchy to get the links.'''
    res = set()
    n = options.L
    while len(res) < n and m != 0:
        scat = choiceCategory(cat, options)
        if scat:
            link = choiceLinks(options.c, scat)
            if link:
                if link not in res:
                    res.add(link)
                    print len(res), link
        m -= 1
    return res


def rmSym(topic):
    '''Remove the prefix "PREFIX:" in topic. This happens when the
    topic has been obtained from a symbolic link'''
    return topic.partition(':')[2] if ':' in topic else topic

def subtopics(structureFileName, cat, subtopic_tags):
    '''return the list of direct subtopics of cat. If there isn't
    such cat then it returns the empty list.'''
    sf = open(structureFileName)
    for _,t in etree.iterparse(sf, tag = ns()+"Topic"):
        if cat == t.attrib[r()+"id"]:
            l = [rmSym(n.attrib[r()+"resource"]) for n in t.iter()
                 if any((st in n.tag) for st in subtopic_tags)]
            t.clear()
            return l
        t.clear()
    sf.close()
    return []

csubtopics = Cache(subtopics, cache_size)

def choiceSubtopic(cat, options):
    '''given a category choose randomly a subcategory from it. p is
    the probability to choose a subcategory which is not a direct
    child of cat. struct_root is the root element of the
    structure.rdf.u8 file.'''
    
    l = csubtopics((options.s, cat, tuple(options.subtopic_tags)))
    p = options.rp
    if l:
        sc = choice(l)
        if random() <= p:
            scr = choiceSubtopic(sc, options)
            if scr:
                sc = scr
        return sc
    else:
        return None


def choiceCategory(cat, options):
    '''like ChoiceSubtopic but consider cat as a result too'''
    p = options.rp
    if random() <= p:
        return choiceSubtopic(cat, options)
    else:
        return cat


def choiceSubtopics(rootTopic, topics, options):
    '''Given an initial set of topics, a insert new subtopics of
    rootTopic randomly chosen'''
    
    while len(topics) < options.S:
        t = choiceSubtopic(rootTopic, options)
        if t not in topics:
            topics.add(t)
            print len(topics),t


def choiceSubtopicsPairs(til, options):
    '''Build set of pairs of positive and negative subtopics from til
    = (ptil, ntil)'''

    spl = set()
    pk = til[0].keys()
    nk = til[1].keys()
    while len(spl) < options.S:
        assert til[0] and til[1]
        p = (choice(pk), choice(nk))
        if p not in spl:
            spl.add(p)
            print len(spl),p
    return spl


def topic_dir(options, topic_id):
    return options.O + "/" + topic_id

def topic_path(options, topic_id):
    return topic_dir(options, topic_id) + "/topic.txt"

def doc_path(options, topic_id, doc_index):
    return topic_dir(options, topic_id) + "/" + "doc_" + str(doc_index)

def doc_path_html(options, topic_id, doc_index):
    return doc_path(options, topic_id, doc_index) + ".html"

def doc_path_txt(options, topic_id, doc_index):
    return doc_path(options, topic_id, doc_index) + ".txt"

def techtc_doc_path(options, topic_id):
    return topic_dir(options, topic_id) + "/techtc_doc.txt"

def wget_cmd(topic_id, doc_index, link, options):
    cmd = "wget"
    cmd += " -r"
    cmd += " -np"
    cmd += " -linf"
    cmd += " -Rgif,jpeg,jpg,png,swf,css,rss,ico,js,wmv,mpeg,mpg,mp3,mov"
    cmd += " -Q" + str(options.Q)
    # the use of ASCCI_strip below is a hacky way to avoid non-ascii
    # addresses
    cmd += " \"" + ASCII_strip(link) + "\""
    cmd += " -O \"" + doc_path_html(options, topic_id, doc_index) + "\""
    # TODO add program options for these parameters
    cmd += " -t 1"              # try only once
    cmd += " --random-wait"
    cmd += " --timeout=3"       # wait 3 sec max
    cmd += " -q"
    # TODO this command doesn't do the right thing (wait no more than 30 sec)
    # cmd += " & sleep 30 && kill ${!}"
    return cmd


def html2text_cmd(topic_id, doc_index, options):
    return globals()[options.H+"_cmd"](topic_id, doc_index, options)


def w3m_cmd(topic_id, doc_index, options):
    cmd = "w3m"
    cmd += " -T text/html"
    cmd += " -dump " + doc_path_html(options, topic_id, doc_index)
    cmd += " > \"" + doc_path_txt(options, topic_id, doc_index) + "\""
    return cmd


def lynx_cmd(topic_id, doc_index, options):
    cmd = "lynx"
    cmd += " -dump " + doc_path_html(options, topic_id, doc_index)
    cmd += " > \"" + doc_path_txt(options, topic_id, doc_index) + "\""
    return cmd


def elinks_cmd(topic_id, doc_index, options):
    cmd = "elinks"
    cmd += " -dump " + doc_path_html(options, topic_id, doc_index)
    cmd += " > \"" + doc_path_txt(options, topic_id, doc_index) + "\""
    return cmd


def links_cmd(topic_id, doc_index, options):
    cmd = "links"
    cmd += " -dump " + doc_path_html(options, topic_id, doc_index)
    cmd += " > \"" + doc_path_txt(options, topic_id, doc_index) + "\""
    return cmd


def links2_cmd(topic_id, doc_index, options):
    cmd = "links2"
    cmd += " -dump " + doc_path_html(options, topic_id, doc_index)
    cmd += " > \"" + doc_path_txt(options, topic_id, doc_index) + "\""
    return cmd


def getId(id_links):
    return id_links[0]


def getLinks(id_links):
    return id_links[1]


def filterTopics(til, minl):
    '''For each topic in til remove it if it doesn't have minl links
    or above.'''

    return {t:til[t] for t in til if len(getLinks(til[t])) >= minl}


def ASCII_strip(s):
    '''Return a string where all non ascii char have been removed'''
    return "".join(c for c in s if ord(c) < 128)


def createDocuments(til, options):
    '''Create documents in techtc format given til, is a dict mapping
    topics and (id, links)'''

    # create directory to put the documents
    if not os.path.exists(options.O):
        print "Create techtc directory"
        mkdir_cmd = "mkdir " + options.O
        print mkdir_cmd
        os.system(mkdir_cmd)

    # total number of links to download
    global total_n_links
    total_n_links = sum([len(getLinks(til[k])) for k in til])
    
    i = 0
    for t in til:
        i += 1
        print "Download all links of",t
        print "Create topic directory"
        t_id = getId(til[t])
        t_dir = topic_dir(options, t_id)
        if not os.path.exists(t_dir):
            mkdir_cmd = "mkdir " + topic_dir(options, t_id)
            print mkdir_cmd
            os.system(mkdir_cmd)
        t_path = topic_path(options, t_id)
        if not os.path.exists(t_path):
            print "Add file containing topic",str(i)+"/"+str(len(til))
            topic_cmd = "echo " + ASCII_strip(t) + " > " + t_path
            print topic_cmd
            os.system(topic_cmd)
        print "Start downloading links"
        t_links = getLinks(til[t])
        downloadLinks(t_id, t_links, options)


def fillTechtcFormatDocument(options, topic_id, doc_index):
    dpt = doc_path_txt(options, topic_id, doc_index)
    # append the document only if it exceeds options.q * options.Q
    dpt_size = os.path.getsize(dpt)
    min_size = int(options.q * options.Q)
    if dpt_size >= min_size:
        tdc = techtc_doc_path(options, topic_id)
        print "Fill document",tdc,"in techtc format"
        rtdc = " >> " + "\"" + tdc + "\""
        cmd = "echo \"<dmoz_doc>\"" + rtdc
        # print cmd
        os.system(cmd)
        cmd = "echo id=" + str(doc_index) + rtdc
        # print cmd
        os.system(cmd)
        cmd = "echo \"<dmoz_subdoc>\"" + rtdc
        # print cmd
        os.system(cmd)
        cmd = "cat " + dpt + rtdc
        # print cmd
        os.system(cmd)
        cmd = "echo \"</dmoz_subdoc>\"" + rtdc
        # print cmd
        os.system(cmd)
        cmd = "echo \"</dmoz_doc>\"" + rtdc
        # print cmd
        os.system(cmd)
    else:
        print "Warning: the size of " + dpt + ", " + str(dpt_size) + " is too low (should be " + str(min_size) + " at least)"


link_idx = 0
total_n_links = 0


# TODO some links are duplicated between topics, we should optimize so
# that they are not downloaded multiple times
def downloadLinks(topic_id, ls, options):
    '''Download links ls and place the content of each link in a file
    under topic_id directory. The files are indexed from 0 to
    len(ls)-1'''

    i = 0
    for l in ls:
        global link_idx
        link_idx += 1
        print "Download link " + str(link_idx) + "/" + str(total_n_links)
        dpt = doc_path_txt(options, topic_id, i)
        if os.path.exists(dpt):
            print "Document", dpt, "has already been downloaded"
        else:
            # download links
            cmd = wget_cmd(topic_id, i, l, options)
            print cmd
            os.system(cmd)
            # convert them into text
            cmd = html2text_cmd(topic_id, i, options)
            print cmd
            os.system(cmd)
            # remove now useless html file
            cmd = "rm \"" + doc_path_html(options, topic_id, i) + "\""
            print cmd
            os.system(cmd)
            # fill document in techtc format for that topic
            fillTechtcFormatDocument(options, topic_id, i)
        i += 1


def dictTopicIdLinks(topics, til, options):
    '''Insert til[topic]=(id, links) for each topic of topics if
    not already in til.'''

    if options.u:               # random link selection
        # TODO add options instead of that ad hoc number
        f = lambda x: choiceCollectLinks(x, options, options.L*100) 
    else:                       # deterministic link selection
        f = lambda x: collectLinksBFS(x, options)

    cf = open(options.c)
    i = 0
    for _,t in etree.iterparse(cf, tag = ns()+"Topic"):
        topic = t.attrib[r()+"id"]
        if topic in topics and topic not in til:
            i += 1
            print "Topic", i
            # get id
            t_id = t.findtext(ns()+"catid")
            print "id("+topic+") =", t_id
            # get links
            t_links = f(topic)
            #  insert mapping
            til[topic] = (t_id, t_links)
        t.clear()
        if len(til) == len(topics): # no need to parse further
            break
    cf.close()
        

def dataset_dir(options, p_id, n_id):
    return options.O + "/" + "Exp_" + p_id + "_" + n_id


def organizeDocuments(spl, til, options):
    for p,n in spl:
        p_id = getId(til[0][p])
        n_id = getId(til[1][n])
        dsd = dataset_dir(options, p_id, n_id)
        dsd_p = dsd + "/all_pos.txt"
        dsd_n = dsd + "/all_neg.txt"
        print "Create dataset directory for " + p + "vs" + n
        cmd = "mkdir " + dsd
        print cmd
        os.system(cmd)
        print "Move the positve documents in it"
        cmd = "cp " + techtc_doc_path(options, p_id) + " " + dsd_p
        print cmd
        os.system(cmd)
        print "Move the negative documents in it"
        cmd = "cp " + techtc_doc_path(options, n_id) + " " + dsd_n
        print cmd
        os.system(cmd)


def buildTopicsIdsLinks(options):
    '''Build a dictionary mapping each topic to pair composed by its
    id and a list of links. Depending on the options a dump file can
    be provided in input so the building process will not start from
    scratch (usefull in case of crashing). For the same reason (if the
    right option is selected it can save preriodically the building in
    to a dump file).'''

    if options.i:               # start from a dump file
        print "The building will start from file", options.i
        inputDumpFile = open(options.i)
        ptil, ntil = pickle.load(inputDumpFile)
    else:                       # start from scratch
        print "No dump file has been provided so the building will start from scratch"
        ptil = {}
        ntil = {}
        
    print "Choose", options.S, "positive subtopics of",options.posCR
    pts = set(ptil.keys())            # positive subtopics
    choiceSubtopics(options.posCR, pts, options)

    print "Choose", options.S, "negative subtopics of",options.negCR
    nts = set(ntil.keys())            # negative subtopics
    choiceSubtopics(options.negCR, nts, options)

    print "Associate id and", options.L, "links to each positive subtopic"
    dictTopicIdLinks(pts, ptil, options)

    print "Associate id and", options.L, "links to each negative subtopic"
    dictTopicIdLinks(nts, ntil, options)

    if options.o:
        with open(options.o, "w") as outputDumpFile:
            pickle.dump((ptil, ntil), outputDumpFile)
    
    minl = int(options.l * options.L)
    print "Remove postive topics with less than", minl, "links"
    ptil_len = len(ptil)
    ptil = filterTopics(ptil, minl)
    print ptil_len - len(ptil), "topics have been removed"

    print "Remove negative topics with less than", minl, "links"
    ntil_len = len(ntil)
    ntil = filterTopics(ntil, minl)
    print ntil_len - len(ntil), "topics have been removed"

    return ptil, ntil


def til_union(til):
    '''Return the union of 2 dict, d2 overwrite d1'''
    til_u = til[0]
    til_u.update(til[1])
    return til_u


def build_techtc(options):

    seed(options.random_seed)   # seed the random generator

    til = buildTopicsIdsLinks(options)

    print "Build", options.S, "pairs of positive and negative topic"
    spl = choiceSubtopicsPairs(til, options)
    
    if not options.P:

        if not options.C:
            print "Create documents in techtc format for all subtopics"
            createDocuments(til_union(til), options)
        else:
            print "Skip creation of documents in techtc format"

        print "Organize documents according to the list of pairs of subtopics"
        organizeDocuments(spl, til, options)


def main():
    usage = "Usage: %prog [Options]"
    parser = OptionParser(usage)
    parser.add_option("-r", "--random-seed",
                      default=1,
                      help="Random seed. [default: %default]")
    parser.add_option("-c", "--content-file",
                      dest="c", default="content_stripped.rdf.u8",
                      help="ODP RDF content file. [default: %default]")
    parser.add_option("-s", "--structure-file",
                      dest="s", default="structure_stripped.rdf.u8",
                      help="ODP RDF structure file. [default: %default]")
    parser.add_option("-p", "--positive-category-root",
                      dest="posCR", default="Top/Arts",
                      help="Category root of the sub-categories used for positive documents. [default: %default]")
    parser.add_option("-n", "--negative-category-root",
                      dest="negCR", default="Top/Science",
                      help="Category root of the sub-categories used for negative documents. [default: %default]")
    parser.add_option("-R", "--recursive-probability", type="float",
                      dest="rp", default=0.5,
                      help="Probability of searching in the ODP in depth. [default: %default]")
    parser.add_option("-S", "--techtc-size", type="int",
                      dest="S", default=300,
                      help="Size of the techtc generated. [default: %default]")
    parser.add_option("-L", "--max-documents", type="int",
                      dest="L", default=200,
                      help="Maximum mumber of documents per category. [default: %default]")
    parser.add_option("-l", "--minimum-proportion-document-number",
                      type="float", dest="l", default=0.6,
                      help="In case enough links cannot be retrieved to reach the right document number (option -L) then what proportion of it we tolerate. [default: %default]")
    parser.add_option("-u", "--random-link-selection",
                      action="store_true", dest="u",
                      help="Select randomly the links within a subcategory instead of in BFS order. This method is much slower.")
    parser.add_option("-o", "--output-dump-file",
                      dest="o", default="",
                      help="File where to dump intermediary results to build techtc. Useful in case of crash. [default: %default]")
    parser.add_option("-i", "--input-dump-file",
                      dest="i", default="",
                      help="Dump file to load so that the process of building the topics and links doesn't start from scratch. If no file is given then it starts from scratch. [default: %default]")
    parser.add_option("-O", "--output-directory",
                      dest="O", default="__default__",
                      help="Directory where to download the web pages and place the dataset collection. [default: techtc_SIZE] where SIZE is the size of the dataset collection given by option S.")
    parser.add_option("-Q", "--quota", type="int",
                      dest="Q", default=100000,
                      help="Maximum number of bytes to retreive per link. [default: %default]")
    parser.add_option("-q", "--minimum-proportion-document-quota",
                      type="float", dest="q", default=0.01,
                      help="Ignore documents with size under the quota (option -Q) * this ratio. [default: %default]")
    parser.add_option("-P", "--only-parse", action="store_true",
                      dest="P",
                      help="Perform only parsing (building of topics and links), do not download web pages, and save the result in the file provided with options -o.")
    parser.add_option("-C", "--not-create-documents", action="store_true",
                      dest="C",
                      help="If the documents have been created but not organized yet (because it takes a lot of disk space) then that option can be used. Normally the recovery and continuation is automatic but with that option the program will not try to create missing intermediate documents therefore they can be deleted to get more space. You need to is specifying the existing output directory with option -O and the dump file with option -i.")
    parser.add_option("-t", "--subtopic-tags", action="append",
                      default=["narrow", "symbolic"],
                      help="Use the following tag prefixes to find subtopics of a given topic.")
    parser.add_option("-H", "--html2text", dest="H",
                      default="w3m",
                      help="Software to convert html into text. The supported softwares are w3m, lynx, elinks, links, links2. [default: %default]")
    (options, args) = parser.parse_args()

    if len(args) != 0:
        parser.error("incorrect number of arguments. Use --help to get more information")

    if options.O == "__default__":
        options.O = "techtc"+str(options.S)

    build_techtc(options)

    # print "Cache failures for links =", clinks.get_failures()
    # print "Cache hits for links =", clinks.get_hits()

    # print "Cache failures for subtopics =", csubtopics.get_failures()
    # print "Cache hits for subtopics =", csubtopics.get_hits()


if __name__ == "__main__":
    main()
