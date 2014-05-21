import unittest
from spitfire.runtime import _udn
from spitfire.runtime import udn


class Foo(object):
  bar = 'win'


class TestCUdn(unittest.TestCase):
  def testResolveHitWithoutException(self):
    self.assertEqual(_udn._resolve_udn(Foo(), 'bar'), 'win')

  def testResolveHitWithException(self):
    self.assertEqual(_udn._resolve_udn(Foo(), 'bar', raise_exception=True),
                     'win')

  def testResolveMissWithoutException(self):
    self.assertIsInstance(_udn._resolve_udn(Foo(), 'missing'),
                          udn.UndefinedAttribute)

  def testResolveMissWithException(self):
    self.assertRaises(udn.UDNResolveError, _udn._resolve_udn, Foo(), 'misssing',
                      raise_exception=True)


if __name__ == '__main__':
  unittest.main()