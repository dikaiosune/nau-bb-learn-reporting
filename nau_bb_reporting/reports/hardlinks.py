__author__ = 'adam'

import logging
from string import ascii_uppercase

import pandas as pd
from bs4 import BeautifulSoup

log = logging.getLogger('nau_bb_reporting.reports.hardlinks')

lazy_query = """
select
    content_items.course_id,
    cc.main_data
from
    (SELECT DISTINCT
        cm.course_id,
        cc.title,
        cc.pk1
    FROM bblearn.course_main cm, bblearn.course_contents cc
    WHERE
        cc.main_data LIKE '%<a%'
        AND cc.crsmain_pk1 = cm.pk1
        AND cm.course_id LIKE :course_id_like
    ) content_items
  JOIN
bblearn.course_contents cc
ON cc.pk1 = content_items.pk1
"""

greedy_query = """
select DISTINCT
  cm.course_id
from bblearn.course_main cm, bblearn.course_contents cc, bblearn.course_contents_files ccf, bblearn.files f
 WHERE
   NOT REGEXP_LIKE(f.link_name,'(DVD|VT|T)[0-9]{2,5}_(.+).html','i')
   AND f.link_name LIKE '%.htm%'
   AND f.pk1 = ccf.files_pk1
   AND ccf.course_contents_pk1 = cc.pk1
   AND cc.cnthndlr_handle = 'resource/x-bb-file'
   AND cc.crsmain_pk1 = cm.pk1
   AND cm.course_id LIKE :course_id_like
"""


def run(term, connection, out_file_path, greedy=False):
    log.info("Running hardlinks report for %s.", term)

    found_course_ids = set()
    course_id_patterns = [term + '-NAU00-' + letter + '%' for letter in ascii_uppercase]

    if greedy:
        log.info('Retreiving a list of %s courses with deployed HTML files...', term)
        greedy_cur = connection.cursor()
        greedy_cur.prepare(greedy_query)

        for pattern in course_id_patterns:
            greedy_cur.execute(None, course_id_like=pattern)
            for row in greedy_cur:
                found_course_ids.add(row[0])

    main_cur = connection.cursor()
    main_cur.prepare(lazy_query)
    log.info('Checking all %s courses for content items with bad links...', term)
    for pattern in course_id_patterns:
        main_cur.execute(None, course_id_like=pattern)
        for row in main_cur:
            course_id = row[0]
            html = row[1]
            if course_id not in found_course_ids and has_hard_links(html):
                found_course_ids.add(course_id)

    log.info('Found all courses, writing to report file.')
    header = ['course id']
    df = pd.DataFrame([x for x in found_course_ids], columns=header)
    df.to_excel(out_file_path, sheet_name=term + ' Hardlink courses', encoding='UTF-8', columns=header)
    log.info('Wrote report to %s', out_file_path)


def has_hard_links(html_content):
    soup = BeautifulSoup(html_content)

    urls = [link.get('href') for link in soup.find_all('a')]
    urls.extend([image.get('src') for image in soup.find_all('img')])

    for link in urls:
        if link is None or len(link) == 0:
            continue

        trimmed = link.replace('%20', ' ').strip()
        if len(trimmed) == 0:
            continue

        url = trimmed.replace(' ', '%20')
        url = url.replace('@X@EmbeddedFile.requestUrlStub@X@', 'https://bblearn.nau.edu/')
        url = url.replace('@X@EmbeddedFile.location@X@', 'https://bblearn.nau.edu/')

        if 'iris.nau.edu/owa/redir.aspx' in url:
            return True

        elif 'xid' in url and 'bbcswebdav' in url:
            continue

        elif (url.startswith('http://') or url.startswith('https://')) and 'bblearn' not in url:
            continue

        elif '/images/ci/' in url:
            continue

        elif ('courses' in url or 'webapps' in url or 'bbcswebdav' in url) \
                and '/execute/viewDocumentation?' not in url \
                and '/wvms-bb-BBLEARN' not in url \
                and '/bb-collaborate-BBLEARN' not in url \
                and '/vtbe-tinymce/tiny_mce' not in url \
                and 'webapps/login' not in url \
                and 'webapps/portal' not in url:
            return True

        elif not url.startswith('https://') and \
                not url.startswith('http://') and \
                not url.startswith('javascript:') and \
                not url.startswith('mailto:') and \
                not url.startswith('#') and \
                not url.startswith('data:image/') and \
                        'webapps' not in url:
            return True

    return False