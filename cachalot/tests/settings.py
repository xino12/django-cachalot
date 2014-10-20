# coding: utf-8

from __future__ import unicode_literals
from django.conf import settings


try:
    from unittest import skipIf
except ImportError:  # For Python 2.6
    from unittest2 import skipIf

from django.db import connection
from django.test import TransactionTestCase

from ..settings import cachalot_settings
from .models import Test


class SettingsTestCase(TransactionTestCase):
    @cachalot_settings(CACHALOT_ENABLED=False)
    def test_decorator(self):
        with self.assertNumQueries(1):
            list(Test.objects.all())
        with self.assertNumQueries(1):
            list(Test.objects.all())

    def test_enabled(self):
        with cachalot_settings(CACHALOT_ENABLED=True):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())

        with cachalot_settings(CACHALOT_ENABLED=False):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(1):
                list(Test.objects.all())

        with self.assertNumQueries(0):
            list(Test.objects.all())

        is_sqlite = connection.vendor == 'sqlite'

        with cachalot_settings(CACHALOT_ENABLED=False):
            with self.assertNumQueries(2 if is_sqlite else 1):
                t = Test.objects.create(name='test')
        with self.assertNumQueries(1):
            data = list(Test.objects.all())
        self.assertListEqual(data, [t])

    @skipIf(len(settings.CACHES) == 1,
            'We can’t change the cache used since there’s only one configured')
    def test_cache(self):
        with cachalot_settings(CACHALOT_CACHE='default'):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())

        other_cache = [k for k in settings.CACHES if k != 'default'][0]

        with cachalot_settings(CACHALOT_CACHE=other_cache):
            with self.assertNumQueries(1):
                list(Test.objects.all())
            with self.assertNumQueries(0):
                list(Test.objects.all())
