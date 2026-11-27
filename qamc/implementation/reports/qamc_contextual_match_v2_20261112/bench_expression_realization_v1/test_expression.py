import unittest

from expression import apply, eligible, locate, restore_format, valid_replacement


class DirectionTest(unittest.TestCase):
    def test_protects_task_priority(self):
        memory = ["The user prefers short, simple responses."]
        self.assertTrue(eligible("Draft a note to the provider.", memory))
        self.assertFalse(eligible("Draft a detailed note to the provider.", memory))
        self.assertFalse(eligible("Draft a note.", ["The user enjoys short hikes."]))

    def test_preserves_salutation_format_and_closing(self):
        original = ("Subject: Request for review\nDear Sir or Madam,\n\n"
                    "I hope that your team can kindly provide information about the available options. "
                    "**Please confirm by Friday so that we can provide supporting information in time.**\n"
                    "Best regards,\nPersonal Name")
        a, = locate(original)
        candidate = "Please provide information about the available options."
        self.assertEqual(original.replace(a.text, candidate), apply(original, (a,), (candidate,)))

    def test_requires_same_protected_values(self):
        original = "Please note that we may need to pay 25 dollars if the request is approved."
        self.assertFalse(valid_replacement(original, "We need to pay 25 dollars."))
        self.assertFalse(valid_replacement(original, "We may need to pay 10 dollars if approved."))
        self.assertTrue(valid_replacement(original, "We may need to pay 25 dollars if approved."))

    def test_does_not_split_titles(self):
        text = "I would be grateful if you could please contact Dr. Baker with the necessary information."
        a, = locate(text)
        self.assertEqual(text, a.text)

    def test_inline_greeting_and_bold_text_remain_exact(self):
        old = ("Dear Team, I hope that you can kindly provide **a copy of the application** "
               "for my review.\nBest,\nSender")
        a, = locate(old)
        replacement = restore_format(a.text, "Please send a copy of the application for my review.")
        self.assertEqual("Dear Team, Please send **a copy of the application** for my review.\nBest,\nSender",
                         apply(old, (a,), (replacement,)))
        self.assertIsNone(restore_format(a.text, "Please provide the application."))


if __name__ == "__main__":
    unittest.main()
