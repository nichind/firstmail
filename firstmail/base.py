import imaplib
import smtplib
import email
import email.mime.text
import email.mime.multipart
import time
from typing import Generator, List, Optional
from contextlib import contextmanager


class EmailMessage:
    """Represents an email message with basic attributes."""

    def __init__(self, subject: str, sender: str, recipient: str, body: str, date: str, message_id: str, raw_message: bytes = None):
        self.subject = subject
        self.sender = sender
        self.recipient = recipient
        self.body = body
        self.date = date
        self.message_id = message_id
        self.raw_message = raw_message

    def __repr__(self):
        return f"EmailMessage(subject='{self.subject}', sender='{self.sender}', date='{self.date}')"


class FirstMail:
    """High-performance IMAP client for firstmail.ltd with automatic resource management."""

    def __init__(self, email: str, password: str, use_ssl: bool = True):
        """
        Initialize FirstMail client.

        Args:
            email: Email address OR "email:password"
            password: Email password
            use_ssl: Whether to use SSL (default: True, port 993)
        """
        self.email = email
        if ":" in self.email and not password:
            self.email, self.password = self.email.split(":", 1)
        else:
            self.password = password
        self.use_ssl = use_ssl

        self.imap_host = "imap.firstmail.ltd"
        self.smtp_host = "imap.firstmail.ltd"
        self.imap_port = 993 if use_ssl else 143
        self.smtp_port = 465 if use_ssl else 587

        self._imap = None
        self._smtp = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.close()

    def _connect_imap(self) -> imaplib.IMAP4:
        """Establish IMAP connection if not already connected."""
        if self._imap is None:
            try:
                if self.use_ssl:
                    self._imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
                else:
                    self._imap = imaplib.IMAP4(self.imap_host, self.imap_port)

                self._imap.login(self.email, self.password)
                self._imap.select("INBOX")
            except Exception as e:
                if self._imap:
                    try:
                        self._imap.logout()
                    except Exception:
                        pass
                    self._imap = None
                raise ConnectionError(f"Failed to connect to IMAP server: {e}")

        return self._imap

    def _connect_smtp(self) -> smtplib.SMTP:
        """Establish SMTP connection if not already connected."""
        if self._smtp is None:
            try:
                if self.use_ssl:
                    self._smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
                else:
                    self._smtp = smtplib.SMTP(self.smtp_host, self.smtp_port)
                    self._smtp.starttls()

                self._smtp.login(self.email, self.password)
            except Exception as e:
                if self._smtp:
                    try:
                        self._smtp.quit()
                    except Exception:
                        pass
                    self._smtp = None
                raise ConnectionError(f"Failed to connect to SMTP server: {e}")

        return self._smtp

    def _parse_email(self, raw_email: bytes) -> EmailMessage:
        """Parse raw email bytes into EmailMessage object."""
        try:
            msg = email.message_from_bytes(raw_email)

            subject = email.header.decode_header(msg.get("Subject", ""))[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode("utf-8", errors="ignore")

            sender = msg.get("From", "")
            recipient = msg.get("To", "")
            date = msg.get("Date", "")
            message_id = msg.get("Message-ID", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")

            return EmailMessage(subject, sender, recipient, body, date, message_id, raw_email)

        except Exception as e:
            return EmailMessage(
                subject="[Parse Error]",
                sender="unknown",
                recipient=self.email,
                body=f"Error parsing email: {e}",
                date="",
                message_id="",
                raw_message=raw_email,
            )

    def get_last_mail(self) -> Optional[EmailMessage]:
        """Get the most recent email message."""
        try:
            imap = self._connect_imap()
            typ, msg_nums = imap.search(None, "ALL")
            if typ != "OK" or not msg_nums[0]:
                return None

            last_msg_num = msg_nums[0].split()[-1]
            typ, msg_data = imap.fetch(last_msg_num, "(RFC822)")
            if typ != "OK":
                return None

            raw_email = msg_data[0][1]
            return self._parse_email(raw_email)

        except Exception as e:
            raise RuntimeError(f"Failed to get last mail: {e}")

    def get_all_mail(self, limit: Optional[int] = None) -> List[EmailMessage]:
        """
        Get all email messages.

        Args:
            limit: Maximum number of messages to retrieve (None for all)

        Returns:
            List of EmailMessage objects, newest first
        """
        try:
            imap = self._connect_imap()
            typ, msg_nums = imap.search(None, "ALL")
            if typ != "OK" or not msg_nums[0]:
                return []

            msg_numbers = msg_nums[0].split()
            if limit:
                msg_numbers = msg_numbers[-limit:]
            msg_numbers.reverse()

            emails = []
            for msg_num in msg_numbers:
                typ, msg_data = imap.fetch(msg_num, "(RFC822)")
                if typ == "OK" and msg_data[0]:
                    raw_email = msg_data[0][1]
                    emails.append(self._parse_email(raw_email))

            return emails

        except Exception as e:
            raise RuntimeError(f"Failed to get all mail: {e}")

    def send_mail(self, to: str, subject: str, body: str, cc: Optional[str] = None, bcc: Optional[str] = None) -> bool:
        """
        Send an email message.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body text
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            smtp = self._connect_smtp()

            msg = email.mime.multipart.MIMEMultipart()
            msg["From"] = self.email
            msg["To"] = to
            msg["Subject"] = subject

            if cc:
                msg["Cc"] = cc

            msg.attach(email.mime.text.MIMEText(body, "plain"))

            recipients = [to]
            if cc:
                recipients.extend([addr.strip() for addr in cc.split(",")])
            if bcc:
                recipients.extend([addr.strip() for addr in bcc.split(",")])

            smtp.send_message(msg, to_addrs=recipients)
            return True

        except Exception as e:
            raise RuntimeError(f"Failed to send mail: {e}")

    def watch_for_new_emails(self, check_interval: int = 5) -> Generator[EmailMessage, None, None]:
        """
        Generator that yields new emails as they arrive.

        Args:
            check_interval: Seconds between checks (default: 30)

        Yields:
            EmailMessage objects for new emails
        """
        seen_ids = set()

        try:
            existing_emails = self.get_all_mail()
            seen_ids.update(email.message_id for email in existing_emails if email.message_id)
        except Exception:
            pass

        while True:
            try:
                current_emails = self.get_all_mail()
                for email_msg in current_emails:
                    if email_msg.message_id and email_msg.message_id not in seen_ids:
                        seen_ids.add(email_msg.message_id)
                        yield email_msg
                time.sleep(check_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error while watching for emails: {e}")
                time.sleep(check_interval)

    def get_message_count(self) -> int:
        """Get total number of messages in inbox."""
        try:
            imap = self._connect_imap()
            typ, msg_nums = imap.search(None, "ALL")
            if typ != "OK" or not msg_nums[0]:
                return 0
            return len(msg_nums[0].split())
        except Exception:
            return 0

    def close(self):
        """Close all connections and clean up resources."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

        if self._smtp:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None


@contextmanager
def firstmail_client(email: str, password: str = None, use_ssl: bool = True):
    """
    Context manager for FirstMail client with automatic cleanup.

    Usage:
        with firstmail_client("user@example.com", "password") as client:
            last_email = client.get_last_mail()
    """
    client = FirstMail(email, password, use_ssl)
    try:
        yield client
    finally:
        client.close()
