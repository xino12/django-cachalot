# coding: utf-8

from __future__ import unicode_literals
from time import sleep
from unittest import skipIf

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import DEFAULT_CACHE_ALIAS
from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import override_settings

from ..api import invalidate
from .models import Test, TestParent, TestChild


class SettingsTestCase(TransactionTestCase):
    def setUp(self):
        if connection.vendor == 'mysql':
            # We need to reopen the connection or Django
            # will execute an extra SQL request below.
            connection.cursor()

    @override_settings(CACHALOT_ENABLED=False)
    def test_decorator(self):
        with self.assertNumQueries(1):
            list(Test.objects.all())
        with self.assertNumQueries(1):
            list(Test.objects.all())

    def test_django_override(self):
        with self.settings(CACHALOT_ENABLED=False):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.settings(CACHALOT_ENABLED=True):
                with self.assertNumQueries(1):
                    list(Test.objects.all())
                with self.assertNumQueries(0):
                    list(Test.objects.all())

    def test_enabled(self):
        with self.settings(CACHALOT_ENABLED=True):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())

        with self.settings(CACHALOT_ENABLED=False):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(1):
                list(Test.objects.all())

        with self.assertNumQueries(0):
            list(Test.objects.all())

        is_sqlite = connection.vendor == 'sqlite'

        with self.settings(CACHALOT_ENABLED=False):
            with self.assertNumQueries(2 if is_sqlite else 1):
                t = Test.objects.create(name='test')
        with self.assertNumQueries(1):
            data = list(Test.objects.all())
        self.assertListEqual(data, [t])

    @skipIf(len(settings.CACHES) == 1,
            'We can’t change the cache used since there’s only one configured')
    def test_cache(self):
        with self.settings(CACHALOT_CACHE=DEFAULT_CACHE_ALIAS):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())

        other_cache_alias = next(alias for alias in settings.CACHES
                                 if alias != DEFAULT_CACHE_ALIAS)

        with self.settings(CACHALOT_CACHE=other_cache_alias):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())

    def test_cache_timeout(self):
        with self.assertNumQueries(1):
            list(Test.objects.all())
        sleep(1)
        with self.assertNumQueries(0):
            list(Test.objects.all())

        invalidate(Test)

        with self.settings(CACHALOT_TIMEOUT=0):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            sleep(0.05)
            with self.assertNumQueries(1):
                list(Test.objects.all())

        # We have to test with a full second and not a shorter time because
        # memcached only takes the integer part of the timeout into account.
        with self.settings(CACHALOT_TIMEOUT=1):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())
            sleep(1)
            with self.assertNumQueries(1):
                list(Test.objects.all())

    def test_cache_random(self):
        with self.assertNumQueries(1):
            list(Test.objects.order_by('?'))
        with self.assertNumQueries(1):
            list(Test.objects.order_by('?'))

        with self.settings(CACHALOT_CACHE_RANDOM=True):
            with self.assertNumQueries(1):
                list(Test.objects.order_by('?'))
            with self.assertNumQueries(0):
                list(Test.objects.order_by('?'))

    def test_invalidate_raw(self):
        with self.assertNumQueries(1):
            list(Test.objects.all())
        with self.settings(CACHALOT_INVALIDATE_RAW=False):
            with self.assertNumQueries(1):
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE %s SET name = 'new name';"
                                   % Test._meta.db_table)
        with self.assertNumQueries(0):
            list(Test.objects.all())

    def test_only_cachable_tables(self):
        with self.settings(CACHALOT_ONLY_CACHABLE_TABLES=('cachalot_test',)):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())

            with self.assertNumQueries(1):
                list(TestParent.objects.all())
            with self.assertNumQueries(1):
                list(TestParent.objects.all())

            with self.assertNumQueries(1):
                list(Test.objects.select_related('owner'))
            with self.assertNumQueries(1):
                list(Test.objects.select_related('owner'))

        with self.assertNumQueries(1):
            list(TestParent.objects.all())
        with self.assertNumQueries(0):
            list(TestParent.objects.all())

        with self.settings(CACHALOT_ONLY_CACHABLE_TABLES=(
                'cachalot_test', 'cachalot_testchild', 'auth_user')):
            with self.assertNumQueries(1):
                list(Test.objects.select_related('owner'))
            with self.assertNumQueries(0):
                list(Test.objects.select_related('owner'))

            # TestChild uses multi-table inheritance, and since its parent,
            # 'cachalot_testparent', is not cachable, a basic
            # TestChild query can’t be cached
            with self.assertNumQueries(1):
                list(TestChild.objects.all())
            with self.assertNumQueries(1):
                list(TestChild.objects.all())

            # However, if we only fetch data from the 'cachalot_testchild'
            # table, it’s cachable.
            with self.assertNumQueries(1):
                list(TestChild.objects.values('public'))
            with self.assertNumQueries(0):
                list(TestChild.objects.values('public'))

    def test_uncachable_tables(self):
        with self.settings(CACHALOT_UNCACHABLE_TABLES=('cachalot_test',)):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(1):
                list(Test.objects.all())

        with self.assertNumQueries(1):
            list(Test.objects.all())
        with self.assertNumQueries(0):
            list(Test.objects.all())

        with self.settings(CACHALOT_UNCACHABLE_TABLES=('cachalot_test',)):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(1):
                list(Test.objects.all())

    def test_only_cachable_and_uncachable_table(self):
        with self.settings(
                CACHALOT_ONLY_CACHABLE_TABLES=('cachalot_test',
                                               'cachalot_testparent'),
                CACHALOT_UNCACHABLE_TABLES=('cachalot_test',)):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(1):
                list(Test.objects.all())

            with self.assertNumQueries(1):
                list(TestParent.objects.all())
            with self.assertNumQueries(0):
                list(TestParent.objects.all())

            with self.assertNumQueries(1):
                list(User.objects.all())
            with self.assertNumQueries(1):
                list(User.objects.all())
