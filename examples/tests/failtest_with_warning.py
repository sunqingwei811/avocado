from avocado import Test


class FailTest(Test):

    """
    Example test for avocado. Straight up fail the test.

    :avocado: tags=failure_expected
    """

    def test(self):
        """
        Should fail.
        """
        self.log.warning("This is warning")
        self.fail("This test is supposed to fail")
