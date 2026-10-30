from datetime import date
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
import app


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch('app.today', return_value=date(2026,10,30))
        self.clock.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.old = app.DB
        app.DB = Path(self.tmp.name) / 'test.sqlite3'
        app.init()
        with app.connect() as db:
            db.execute("INSERT INTO labs(name) VALUES('Scienze')")
        app.create_user('docente', 'Docente', 'password-test-123')
        self.user = {'id': 1, 'name': 'Docente'}
        self.data = dict(lab=1, teacher='Docente', school_class='2B', start='2026-11-02T09:00', end='2026-11-02T10:00')

    def tearDown(self):
        app.DB = self.old
        self.tmp.cleanup()
        self.clock.stop()

    def test_persistence(self):
        ident = app.book(self.data, self.user)
        app.init()
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT teacher FROM bookings WHERE id=?', (ident,)).fetchone()[0], 'Docente')

    def test_overlap_rejected(self):
        app.book(self.data, self.user)
        with self.assertRaisesRegex(ValueError, 'già prenotato'):
            app.book({**self.data, 'start': '2026-11-02T09:00', 'end': '2026-11-02T10:00'}, self.user)

    def test_adjacent_allowed(self):
        app.book(self.data, self.user)
        app.book({**self.data, 'start': '2026-11-02T10:00', 'end': '2026-11-02T11:00'}, self.user)

    def test_reversed_time_rejected(self):
        with self.assertRaises(ValueError):
            app.book({**self.data, 'end': '2026-11-02T08:00'}, self.user)

    def test_missing_lab_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inesistente'):
            app.book({**self.data, 'lab': 900}, self.user)

    def test_school_rules(self):
        for start,end in [('2026-11-07T09:00','2026-11-07T10:00'),
                          ('2026-11-02T07:00','2026-11-02T08:00'),
                          ('2026-11-02T14:00','2026-11-02T15:00'),
                          ('2026-11-02T09:30','2026-11-02T10:30'),
                          ('2026-11-02T09:00','2026-11-02T11:00')]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                app.book({**self.data, 'start':start,'end':end}, self.user)

    def test_teacher_comes_from_account(self):
        ident = app.book({**self.data, 'teacher':'Altro docente'}, self.user)
        with app.connect() as db:
            row = db.execute('SELECT teacher,user_id FROM bookings WHERE id=?',(ident,)).fetchone()
            self.assertEqual(tuple(row), ('Docente',1))

    def test_catalog_repeatable(self):
        app.init()
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM labs WHERE name IN (?,?,?,?,?)', app.LABS).fetchone()[0],5)

    def test_booking_window(self):
        for start,end in [('2026-10-29T09:00','2026-10-29T10:00'), ('2026-12-01T09:00','2026-12-01T10:00')]:
            with self.subTest(start=start), self.assertRaisesRegex(ValueError, 'mese di calendario'):
                app.book({**self.data,'start':start,'end':end}, self.user)
        app.book({**self.data,'start':'2026-11-30T09:00','end':'2026-11-30T10:00'}, self.user)

    def test_retention_boundary(self):
        with app.connect() as db:
            for day in ('2026-09-29','2026-09-30','2026-10-01'):
                db.execute('INSERT INTO bookings(lab,teacher,school_class,start,end) VALUES(?,?,?,?,?)',
                           (1,'Docente','2B',day+'T09:00',day+'T10:00'))
        app.purge_old()
        with app.connect() as db:
            self.assertEqual([r['start'][:10] for r in db.execute('SELECT start FROM bookings ORDER BY start')],['2026-09-30','2026-10-01'])

    def test_calendar_month_end(self):
        self.assertEqual(app.month_shift(date(2027,1,31),1),date(2027,2,28))
        self.assertEqual(app.month_shift(date(2028,3,31),-1),date(2028,2,29))

    def test_multiple_nonconsecutive_hours(self):
        ids = app.book_many({**self.data,'date':'2026-11-02','hours':[13,8,10]}, self.user)
        self.assertEqual(len(ids),3)
        with app.connect() as db:
            rows=db.execute('SELECT start,end,user_id FROM bookings ORDER BY start').fetchall()
            self.assertEqual([r['start'][11:16] for r in rows],['08:00','10:00','13:00'])
            self.assertTrue(all(r['user_id']==1 for r in rows))

    def test_multiple_conflict_rolls_back_every_hour(self):
        app.book(self.data,self.user)
        with self.assertRaisesRegex(ValueError,'già prenotato'):
            app.book_many({**self.data,'date':'2026-11-02','hours':[8,9,10]}, self.user)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM bookings').fetchone()[0],1)

    def test_multiple_invalid_selection(self):
        for hours in ([],[8,8],[7],[14],[8.5],[True],['8'],None,'8,9'):
            with self.subTest(hours=hours),self.assertRaises(ValueError):
                app.book_many({**self.data,'date':'2026-11-02','hours':hours},self.user)
        with self.assertRaises(ValueError):
            app.book_many({**self.data,'date':'2026-11-07','hours':[8,9]},self.user)

    def test_editing_remains_one_hour(self):
        ident=app.book(self.data,self.user)
        with self.assertRaises(ValueError):
            app.book_many({**self.data,'date':'2026-11-02','hours':[10,11]},self.user,ident)
        app.book_many({**self.data,'date':'2026-11-02','hours':[10]},self.user,ident)
        with app.connect() as db:
            row=db.execute('SELECT start FROM bookings WHERE id=?',(ident,)).fetchone()
            self.assertEqual(row['start'],'2026-11-02T10:00')
