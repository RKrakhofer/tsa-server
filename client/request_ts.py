"""Simple client that posts data to TSA server and prints the token."""
import argparse
import requests


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:5000/tsa")
    p.add_argument("--data", default="hello world")
    args = p.parse_args()
    r = requests.post(args.url, data=args.data.encode())
    print(r.status_code)
    print(r.text)


if __name__ == "__main__":
    main()
