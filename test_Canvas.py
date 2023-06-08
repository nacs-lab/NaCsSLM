from lib import Canvas

import unittest
import numpy as np

class TestCanvas(unittest.TestCase):
    def test_initialization(self):
        cv = Canvas.Canvas([2,3])
        self.assertEqual(cv.shape(), (2,3))
        self.assertIsNone(np.testing.assert_array_equal(cv.get_amp(), np.zeros([2,3])))
        self.assertIsNone(np.testing.assert_array_equal(cv.get_phase(), np.zeros([2,3])))

    def test_add_to_Canvas(self):
        cv = Canvas.Canvas([2,3])
        arr1 = np.array([[2,4,1], [-3, 4, 7]])
        arr2 = np.array([[1,0,-9], [-4, 2, 6]])
        cv.add_amp(arr1)
        self.assertIsNone(np.testing.assert_array_equal(cv.get_amp(), arr1))
        cv.add_amp(arr2)
        self.assertIsNone(np.testing.assert_array_equal(cv.get_amp(), arr1 + arr2))
        cv.add_phase(arr2)
        self.assertIsNone(np.testing.assert_array_equal(cv.get_phase(), arr2))

        def fn(x,y):
            return x**2 + y**2

        cv.replace_amp(np.zeros([2,3]))

        cv.add_fn_to_amp(fn)

        res = np.array([[0, 1, 4], [1, 2, 5]])
        self.assertIsNone(np.testing.assert_array_equal(cv.get_amp(), res))

if __name__ == '__main__':
    unittest.main()
    print('Tests succeeded')
