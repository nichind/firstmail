import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the path to import firstmail
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firstmail.base import FirstMail, EmailMessage, firstmail_client


class TestEmailMessage(unittest.TestCase):
    def test_email_message_creation(self):
        """Test EmailMessage object creation."""
        msg = EmailMessage(
            subject="Test Subject",
            sender="test@example.com",
            recipient="user@example.com",
            body="Test body",
            date="Mon, 1 Jan 2024 12:00:00 +0000",
            message_id="<test@example.com>",
        )

        self.assertEqual(msg.subject, "Test Subject")
        self.assertEqual(msg.sender, "test@example.com")
        self.assertEqual(msg.recipient, "user@example.com")
        self.assertEqual(msg.body, "Test body")
        self.assertEqual(msg.date, "Mon, 1 Jan 2024 12:00:00 +0000")
        self.assertEqual(msg.message_id, "<test@example.com>")

    def test_email_message_repr(self):
        """Test EmailMessage string representation."""
        msg = EmailMessage(
            subject="Test",
            sender="test@example.com",
            recipient="user@example.com",
            body="Body",
            date="Mon, 1 Jan 2024 12:00:00 +0000",
            message_id="<test@example.com>",
        )

        repr_str = repr(msg)
        self.assertIn("Test", repr_str)
        self.assertIn("test@example.com", repr_str)


class TestFirstMail(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.email = "test@firstmail.ltd"
        self.password = "testpassword"
        self.client = FirstMail(self.email, self.password)

    def test_firstmail_initialization(self):
        """Test FirstMail client initialization."""
        self.assertEqual(self.client.email, self.email)
        self.assertEqual(self.client.password, self.password)
        self.assertEqual(self.client.imap_host, "imap.firstmail.ltd")
        self.assertEqual(self.client.imap_port, 993)
        self.assertTrue(self.client.use_ssl)

    def test_firstmail_initialization_no_ssl(self):
        """Test FirstMail client initialization without SSL."""
        client = FirstMail(self.email, self.password, use_ssl=False)
        self.assertEqual(client.imap_port, 143)
        self.assertEqual(client.smtp_port, 587)
        self.assertFalse(client.use_ssl)

    def test_context_manager(self):
        """Test FirstMail as context manager."""
        with patch.object(self.client, "close") as mock_close:
            with self.client as client:
                self.assertIs(client, self.client)
            mock_close.assert_called_once()

    @patch("firstmail.base.imaplib.IMAP4_SSL")
    def test_connect_imap_success(self, mock_imap):
        """Test successful IMAP connection."""
        mock_conn = Mock()
        mock_imap.return_value = mock_conn

        result = self.client._connect_imap()

        mock_imap.assert_called_once_with("imap.firstmail.ltd", 993)
        mock_conn.login.assert_called_once_with(self.email, self.password)
        mock_conn.select.assert_called_once_with("INBOX")
        self.assertEqual(result, mock_conn)

    @patch("firstmail.base.imaplib.IMAP4_SSL")
    def test_connect_imap_failure(self, mock_imap):
        """Test IMAP connection failure."""
        mock_imap.side_effect = Exception("Connection failed")

        with self.assertRaises(ConnectionError):
            self.client._connect_imap()

    @patch("firstmail.base.smtplib.SMTP_SSL")
    def test_connect_smtp_success(self, mock_smtp):
        """Test successful SMTP connection."""
        mock_conn = Mock()
        mock_smtp.return_value = mock_conn

        result = self.client._connect_smtp()

        mock_smtp.assert_called_once_with("imap.firstmail.ltd", 465)
        mock_conn.login.assert_called_once_with(self.email, self.password)
        self.assertEqual(result, mock_conn)

    def test_parse_email_simple(self):
        """Test parsing a simple email."""
        raw_email = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>

This is the email body.
"""

        parsed = self.client._parse_email(raw_email)

        self.assertEqual(parsed.subject, "Test Subject")
        self.assertEqual(parsed.sender, "sender@example.com")
        self.assertEqual(parsed.recipient, "recipient@example.com")
        self.assertEqual(parsed.body.strip(), "This is the email body.")
        self.assertEqual(parsed.date, "Mon, 1 Jan 2024 12:00:00 +0000")
        self.assertEqual(parsed.message_id, "<test@example.com>")

    @patch.object(FirstMail, "_connect_imap")
    def test_get_last_mail_success(self, mock_connect):
        """Test getting last mail successfully."""
        mock_imap = Mock()
        mock_connect.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1 2 3"])
        mock_imap.fetch.return_value = ("OK", [(None, b"test email data")])

        with patch.object(self.client, "_parse_email") as mock_parse:
            mock_email = Mock()
            mock_parse.return_value = mock_email

            result = self.client.get_last_mail()

            mock_imap.search.assert_called_once_with(None, "ALL")
            mock_imap.fetch.assert_called_once_with(b"3", "(RFC822)")
            mock_parse.assert_called_once_with(b"test email data")
            self.assertEqual(result, mock_email)

    @patch.object(FirstMail, "_connect_imap")
    def test_get_last_mail_no_messages(self, mock_connect):
        """Test getting last mail when no messages exist."""
        mock_imap = Mock()
        mock_connect.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b""])

        result = self.client.get_last_mail()

        self.assertIsNone(result)

    @patch.object(FirstMail, "_connect_imap")
    def test_get_all_mail_with_limit(self, mock_connect):
        """Test getting all mail with limit."""
        mock_imap = Mock()
        mock_connect.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1 2 3 4 5"])
        mock_imap.fetch.side_effect = [
            ("OK", [(None, b"email5")]),
            ("OK", [(None, b"email4")]),
        ]

        with patch.object(self.client, "_parse_email") as mock_parse:
            mock_parse.side_effect = [Mock(), Mock()]

            result = self.client.get_all_mail(limit=2)

            self.assertEqual(len(result), 2)
            mock_imap.fetch.assert_any_call(b"5", "(RFC822)")
            mock_imap.fetch.assert_any_call(b"4", "(RFC822)")

    @patch.object(FirstMail, "_connect_smtp")
    def test_send_mail_success(self, mock_connect):
        """Test sending mail successfully."""
        mock_smtp = Mock()
        mock_connect.return_value = mock_smtp

        result = self.client.send_mail(to="recipient@example.com", subject="Test Subject", body="Test body")

        self.assertTrue(result)
        mock_smtp.send_message.assert_called_once()

    def test_get_message_count(self):
        """Test getting message count."""
        with patch.object(self.client, "_connect_imap") as mock_connect:
            mock_imap = Mock()
            mock_connect.return_value = mock_imap
            mock_imap.search.return_value = ("OK", [b"1 2 3 4 5"])

            count = self.client.get_message_count()

            self.assertEqual(count, 5)

    def test_close(self):
        """Test closing connections."""
        mock_imap = Mock()
        mock_smtp = Mock()
        self.client._imap = mock_imap
        self.client._smtp = mock_smtp

        self.client.close()

        mock_imap.logout.assert_called_once()
        mock_smtp.quit.assert_called_once()
        self.assertIsNone(self.client._imap)
        self.assertIsNone(self.client._smtp)


class TestFirstMailContextManager(unittest.TestCase):
    def test_firstmail_client_context_manager(self):
        """Test the firstmail_client context manager function."""
        with patch("firstmail.base.FirstMail") as MockFirstMail:
            mock_client = Mock()
            MockFirstMail.return_value = mock_client

            with firstmail_client("test@example.com", "password") as client:
                self.assertEqual(client, mock_client)

            MockFirstMail.assert_called_once_with("test@example.com", "password", True)
            mock_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
