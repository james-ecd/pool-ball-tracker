import sqlite3

db_name = 'notifications'
conn = sqlite3.connect('%s.db' % db_name)
c = conn.cursor()
c.execute('''CREATE TABLE notifications (name text, slackid text, expiry integer)''')
print('Database: %s.db created and initilized' % db_name)
