import argparse
import getpass
import sys
import json
from typing import Optional

from .base import firstmail_client


def get_credentials(email: Optional[str] = None, password: Optional[str] = None) -> tuple[str, str]:
    """Get email credentials from user input if not provided."""
    if not email:
        email = input("Email: ")

    if not password:
        password = getpass.getpass("Password: ")

    return email, password


def cmd_read_last(args):
    """Read the last/most recent email."""
    email, password = get_credentials(args.email, args.password)

    try:
        with firstmail_client(email, password, args.ssl) as client:
            last_mail = client.get_last_mail()

            if not last_mail:
                print("No emails found.")
                return

            if args.json:
                print(
                    json.dumps(
                        {
                            "subject": last_mail.subject,
                            "sender": last_mail.sender,
                            "recipient": last_mail.recipient,
                            "date": last_mail.date,
                            "body": last_mail.body,
                        },
                        indent=2,
                    )
                )
            else:
                print(f"Subject: {last_mail.subject}")
                print(f"From: {last_mail.sender}")
                print(f"To: {last_mail.recipient}")
                print(f"Date: {last_mail.date}")
                print("-" * 50)
                print(last_mail.body)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_read_all(args):
    """Read all emails."""
    email, password = get_credentials(args.email, args.password)

    try:
        with firstmail_client(email, password, args.ssl) as client:
            emails = client.get_all_mail(args.limit)

            if not emails:
                print("No emails found.")
                return

            if args.json:
                email_list = []
                for mail in emails:
                    email_list.append(
                        {
                            "subject": mail.subject,
                            "sender": mail.sender,
                            "recipient": mail.recipient,
                            "date": mail.date,
                            "body": mail.body if args.full else mail.body[:100] + "..." if len(mail.body) > 100 else mail.body,
                        }
                    )
                print(json.dumps(email_list, indent=2))
            else:
                for i, mail in enumerate(emails, 1):
                    print(f"\n[{i}] Subject: {mail.subject}")
                    print(f"    From: {mail.sender}")
                    print(f"    Date: {mail.date}")
                    if args.full:
                        print("-" * 50)
                        print(mail.body)
                        print("-" * 50)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_send(args):
    """Send an email."""
    email, password = get_credentials(args.email, args.password)

    to_email = args.to or input("To: ")
    subject = args.subject or input("Subject: ")

    if args.body:
        body = args.body
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                body = f.read()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Enter message body (Ctrl+D or Ctrl+Z to finish):")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            body = "\n".join(lines)

    try:
        with firstmail_client(email, password, args.ssl) as client:
            success = client.send_mail(to_email, subject, body, args.cc, args.bcc)

            if success:
                print("Email sent successfully!")
            else:
                print("Failed to send email.", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_watch(args):
    """Watch for new emails."""
    email, password = get_credentials(args.email, args.password)

    try:
        with firstmail_client(email, password, args.ssl) as client:
            print(f"Watching for new emails... (checking every {args.interval} seconds)")
            print("Press Ctrl+C to stop")

            for new_email in client.watch_for_new_emails(args.interval):
                print("\nNew email received!")
                print(f"Subject: {new_email.subject}")
                print(f"From: {new_email.sender}")
                print(f"Date: {new_email.date}")

                if args.show_body:
                    print("-" * 30)
                    print(new_email.body[:200] + "..." if len(new_email.body) > 200 else new_email.body)
                    print("-" * 30)

    except KeyboardInterrupt:
        print("\nStopping email watch.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_count(args):
    """Count total messages in inbox."""
    email, password = get_credentials(args.email, args.password)

    try:
        with firstmail_client(email, password, args.ssl) as client:
            count = client.get_message_count()
            print(f"Total messages in inbox: {count}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FirstMail IMAP client - High-performance email client for firstmail.ltd",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s read-last                    # Read the most recent email
  %(prog)s read-all --limit 10          # Read last 10 emails
  %(prog)s send --to user@example.com   # Send an email interactively
  %(prog)s watch --interval 60          # Watch for new emails every minute
  %(prog)s count                        # Count total messages
        """,
    )

    parser.add_argument("-e", "--email", help="Email address")
    parser.add_argument("-p", "--password", help="Email password (will prompt if not provided)")
    parser.add_argument("--no-ssl", dest="ssl", action="store_false", default=True, help="Disable SSL (use port 143 instead of 993)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser_read_last = subparsers.add_parser("read-last", aliases=["last"], help="Read the most recent email")
    parser_read_last.add_argument("--json", action="store_true", help="Output in JSON format")
    parser_read_last.set_defaults(func=cmd_read_last)

    parser_read_all = subparsers.add_parser("read-all", aliases=["all"], help="Read all emails")
    parser_read_all.add_argument("--limit", type=int, help="Maximum number of emails to read")
    parser_read_all.add_argument("--full", action="store_true", help="Show full email bodies")
    parser_read_all.add_argument("--json", action="store_true", help="Output in JSON format")
    parser_read_all.set_defaults(func=cmd_read_all)

    parser_send = subparsers.add_parser("send", help="Send an email")
    parser_send.add_argument("--to", help="Recipient email address")
    parser_send.add_argument("--subject", help="Email subject")
    parser_send.add_argument("--body", help="Email body text")
    parser_send.add_argument("--file", help="Read body from file")
    parser_send.add_argument("--cc", help="CC recipients (comma-separated)")
    parser_send.add_argument("--bcc", help="BCC recipients (comma-separated)")
    parser_send.set_defaults(func=cmd_send)

    parser_watch = subparsers.add_parser("watch", help="Watch for new emails")
    parser_watch.add_argument("--interval", type=int, default=30, help="Check interval in seconds (default: 30)")
    parser_watch.add_argument("--show-body", action="store_true", help="Show email body preview")
    parser_watch.set_defaults(func=cmd_watch)

    parser_count = subparsers.add_parser("count", help="Count total messages in inbox")
    parser_count.set_defaults(func=cmd_count)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
