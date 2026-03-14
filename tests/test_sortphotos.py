import unittest
from datetime import datetime, timedelta
from src.sortphotos import parse_date_exif, get_oldest_timestamp, check_for_early_morning_photos


class TestParseDateExif(unittest.TestCase):

    def test_basic_datetime(self):
        result = parse_date_exif('2010:06:01 14:30:00')
        self.assertEqual(result, datetime(2010, 6, 1, 14, 30, 0))

    def test_date_only(self):
        result = parse_date_exif('2010:06:01')
        self.assertEqual(result, datetime(2010, 6, 1, 12, 0, 0))  # defaults to noon

    def test_timezone_plus(self):
        result = parse_date_exif('2010:06:01 14:30:00+05:00')
        # +05:00 means subtract 5 hours to get UTC
        self.assertEqual(result, datetime(2010, 6, 1, 9, 30, 0))

    def test_timezone_minus(self):
        result = parse_date_exif('2010:06:01 14:30:00-05:00')
        # -05:00 means add 5 hours to get UTC
        self.assertEqual(result, datetime(2010, 6, 1, 19, 30, 0))

    def test_timezone_z(self):
        result = parse_date_exif('2010:06:01 14:30:00Z')
        # Z means UTC, no adjustment
        self.assertEqual(result, datetime(2010, 6, 1, 14, 30, 0))

    def test_fractional_seconds(self):
        result = parse_date_exif('2010:06:01 14:30:05.123')
        self.assertEqual(result, datetime(2010, 6, 1, 14, 30, 5))

    def test_hour_minute_only(self):
        result = parse_date_exif('2010:06:01 14:30')
        self.assertEqual(result, datetime(2010, 6, 1, 14, 30, 0))

    def test_zero_date(self):
        result = parse_date_exif('0000:00:00 00:00:00')
        self.assertIsNone(result)

    def test_empty_string(self):
        result = parse_date_exif('')
        self.assertIsNone(result)

    def test_none_input(self):
        result = parse_date_exif(None)
        self.assertIsNone(result)

    def test_numeric_input(self):
        result = parse_date_exif(12345)
        self.assertIsNone(result)

    def test_invalid_date(self):
        result = parse_date_exif('2010:13:01 14:30:00')  # month 13
        self.assertIsNone(result)

    def test_invalid_day(self):
        result = parse_date_exif('2010:02:30 14:30:00')  # Feb 30
        self.assertIsNone(result)

    def test_decimal_in_date(self):
        # timestamps with only time but no date have decimals
        result = parse_date_exif('12.34:56:78')
        self.assertIsNone(result)

    def test_too_few_date_parts(self):
        result = parse_date_exif('2010:06')
        self.assertIsNone(result)

    def test_whitespace_handling(self):
        result = parse_date_exif('  2010:06:01 14:30:00  ')
        self.assertEqual(result, datetime(2010, 6, 1, 14, 30, 0))

    def test_very_old_date(self):
        # very old dates may or may not be parseable depending on platform
        result = parse_date_exif('0001:01:01 00:00:00')
        # if it parses, it should be a valid datetime
        if result is not None:
            self.assertEqual(result.year, 1)


class TestGetOldestTimestamp(unittest.TestCase):

    def test_single_date(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(src, '/path/to/photo.jpg')
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))
        self.assertEqual(keys, ['EXIF:CreateDate'])

    def test_multiple_dates_picks_oldest(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
            'EXIF:ModifyDate': '2012:01:15 10:00:00',
            'EXIF:DateTimeOriginal': '2009:03:20 08:00:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(date, datetime(2009, 3, 20, 8, 0, 0))
        self.assertEqual(keys, ['EXIF:DateTimeOriginal'])

    def test_equal_dates_collects_keys(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
            'EXIF:DateTimeOriginal': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))
        self.assertIn('EXIF:CreateDate', keys)
        self.assertIn('EXIF:DateTimeOriginal', keys)

    def test_ignores_gps_tags(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:GPSDateTime': '2005:01:01 00:00:00',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))
        self.assertNotIn('EXIF:GPSDateTime', keys)

    def test_ignores_icc_profile(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'ICC_Profile:ProfileDateTime': '2000:01:01 00:00:00',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))

    def test_ignores_specified_groups(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'File:FileModifyDate': '2005:01:01 00:00:00',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, ['File'], [])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))

    def test_ignores_specified_tags(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:CreateDate': '2005:01:01 00:00:00',
            'EXIF:ModifyDate': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], ['EXIF:CreateDate'])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))
        self.assertEqual(keys, ['EXIF:ModifyDate'])

    def test_no_valid_dates(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:SomeTag': 'not a date',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertIsNone(date)

    def test_date_as_list(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'EXIF:CreateDate': ['2010:06:01 14:30:00', '2012:01:01 00:00:00'],
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))

    def test_ignores_history_when(self):
        data = {
            'SourceFile': '/path/to/photo.jpg',
            'XMP:HistoryWhen': '2000:01:01 00:00:00',
            'EXIF:CreateDate': '2010:06:01 14:30:00',
        }
        src, date, keys = get_oldest_timestamp(data, [], [])
        self.assertEqual(date, datetime(2010, 6, 1, 14, 30, 0))


class TestCheckForEarlyMorningPhotos(unittest.TestCase):

    def test_no_adjustment_when_after_day_begins(self):
        date = datetime(2010, 6, 1, 10, 0, 0)  # 10 AM
        result = check_for_early_morning_photos(date, 4)
        self.assertEqual(result, date)

    def test_adjustment_when_before_day_begins(self):
        date = datetime(2010, 6, 2, 2, 0, 0)  # 2 AM on June 2
        result = check_for_early_morning_photos(date, 4)
        # should be pushed to previous day
        self.assertEqual(result.day, 1)
        self.assertEqual(result.month, 6)

    def test_no_adjustment_at_midnight_with_default(self):
        date = datetime(2010, 6, 1, 0, 0, 0)
        result = check_for_early_morning_photos(date, 0)
        self.assertEqual(result, date)

    def test_exact_boundary(self):
        date = datetime(2010, 6, 1, 4, 0, 0)  # exactly at day_begins
        result = check_for_early_morning_photos(date, 4)
        self.assertEqual(result, date)  # not less than, so no adjustment


if __name__ == '__main__':
    unittest.main()
