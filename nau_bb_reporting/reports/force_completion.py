"""
This report gets us a list (either entire or by term) of all tests that
have Force Completion enabled. It also lists the path where they are deployed
in the course.

Two queries are needed because Oracle doesn't like joining against
hierarchical subqueries. First we go to the database and get a list of tests
with Force Completion enabled, and then we go back for each of those tests
to find out where they are deployed in their course.
"""

__author__ = 'adam'

import logging
from string import ascii_lowercase

import pandas as pd

log = logging.getLogger('nau_bb_reporting.reports.force_completion')

# here we get the list of tests that have FC
first_query = """
SELECT DISTINCT
    u.user_id,
    u.firstname,
    u.lastname,
    u.email,
    cm.course_id,
    cm.course_name,
    cc.title,
    cc.pk1
FROM bblearn.course_assessment ca, bblearn.course_main cm, bblearn.users u, bblearn.course_users cu,
  bblearn.course_contents cc, bblearn.link l
WHERE
    cc.cnthndlr_handle LIKE 'resource/x-bb-asmt-%-link'
    AND cc.pk1 = l.course_contents_pk1
    AND l.link_source_table = 'COURSE_ASSESSMENT'
    AND l.link_source_pk1 = ca.pk1
    AND ca.force_completion_ind = 'Y'
    AND ca.crsmain_pk1 = cm.pk1
    AND cm.course_id LIKE :course_id_like
    AND cu.crsmain_pk1 = cm.pk1
    AND cu.role = 'P'
    AND u.pk1 = cu.users_pk1
    AND u.user_id LIKE :user_id_like
ORDER BY u.user_id ASC
"""

# here we find out where they're deployed in the course
path_query = """
SELECT
  PATH
FROM (
  SELECT
    SYS_CONNECT_BY_PATH(cc.title, '><') "PATH",
    CONNECT_BY_ISLEAF          "LEAF"
  FROM bblearn.course_contents cc
  START WITH cc.pk1 = :test_pk1
  CONNECT BY PRIOR cc.parent_pk1 = cc.pk1
)
WHERE LEAF = 1
"""

# this keeps pandas writing the file in the correct order
result_columns = ['PI UID', 'PI First Name', 'PI Last Name', 'PI Email',
                  'Course ID', 'Course Name', 'Test Name', 'Path to Test']


def run(term, connection, out_file_path):
    log.info("Running force completion report for %s.", term)
    main_cur = connection.cursor()
    main_cur.prepare(first_query)

    # we don't need a pattern to check all terms
    if term != 'all':
        course_id_like = term + '-NAU00-%'
    else:
        course_id_like = '%'

    results = []
    # get all of the tests, batching by first letter of username of PI
    for letter in ascii_lowercase:
        user_id_like = letter + '%'
        main_cur.execute(None, course_id_like=course_id_like, user_id_like=user_id_like)
        results.extend([dict(zip(result_columns, row)) for row in main_cur.fetchall()])

    log.info("Found all %s tests with Force Completion.", term)
    log.info("Finding paths to tests in courses...")

    # find where each test is
    sub_cur = connection.cursor()
    sub_cur.prepare(path_query)
    for row in results:
        # Path to Test stores the content item PK1 in the previous query
        sub_cur.execute(None, test_pk1=row['Path to Test'])
        reverse_path = sub_cur.fetchone()[0]

        # the hierarchical query returns the path in reverse
        # also the database stores certain page names as these constant strings
        path_list = list(reversed(reverse_path.split("><")))
        path_list = [e.replace(
            'VISTA_ORGANIZER_PAGES.label', 'Course Content').replace(
            'COURSE_DEFAULT.Content.CONTENT_LINK.label', 'Content') for e in path_list]

        row['Path to Test'] = " > ".join(path_list[:-2])

    df = pd.DataFrame(results)

    log.info("Writing to excel file...")
    df.to_excel(out_file_path, columns=result_columns, index=False,
                encoding='UTF-8', na_rep='N/A')

    log.info("Done with force completion report!")
