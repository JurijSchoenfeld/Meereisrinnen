# In this module we store information that might be useful to characterise areas or time spans.

case1 = ['20200216', '20200217', '20200218', '20200219', '20200220', '20200221', '20200222']
extent1 = [90, -10, 90, 70]
case2 = ['20200114', '20200115', '20200116', '20200117', '20200118', '20200119', '20200120']
extent2 = [80, 0, 80, 75]
case3 = ['20200128', '20200129', '20200130', '20200131', '20200201', '20200202', '20200203']
extent3 = [70, -10, 90, 70]
case4 = ['20200308', '20200309', '20200310', '20200311', '20200312', '20200313', '20200314', '20200315', '20200316']
extent4 = [65, 0, 80, 75]

barent_extent = (100, -10, 85, 70)
s_extent = (50, 27, 81, 73)
arctic_extent = (180, -180, 90, 60)

extent_dict = {barent_extent: 'Barent sea', s_extent: 'small extent', arctic_extent: 'Arctic'}

Nov = ['20191102', '20191130']
Dec = ['20191201', '20191231']
Jan = ['20200101', '20200131']
Feb = ['20200201', '20200229']
Mar = ['20200301', '20200331']
Apr = ['20200401', '20200430']
Mon = [Nov, Dec, Jan, Feb, Mar, Apr]
