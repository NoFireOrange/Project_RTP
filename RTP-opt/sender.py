import argparse
import socket
import sys
import time

from utils import PacketHeader, compute_checksum

START, END, DATA, ACK = 0, 1, 2, 3
HEADER_LEN = 16
MAX_DATA = 1472 - HEADER_LEN
TIMEOUT = 0.5

def make_packet(pkt_type, seq_num, data=b""):
    """Build a packet (header + data) as bytes, checksum filled in."""
    header = PacketHeader(type=pkt_type, seq_num=seq_num, length=len(data))
    header.checksum = compute_checksum(header / data)
    return bytes(header / data)

def parse_packet(raw):
    if len(raw) < HEADER_LEN:
        return None
    header = PacketHeader(raw[:HEADER_LEN])
    data = raw[HEADER_LEN:HEADER_LEN + header.length]
    if len(data) != header.length:
        return None
    recv_checksum = header.checksum
    header.checksum = 0
    if compute_checksum(header / data) != recv_checksum:
        return None
    return header.type, header.seq_num, data


def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (receiver_ip, receiver_port)
    message = sys.stdin.buffer.read()
    chunks = [message[i:i + MAX_DATA] for i in range(0, len(message), MAX_DATA)]
    total = len(chunks)
    packets = {i + 1: make_packet(DATA, i + 1, chunks[i]) for i in range(total)}
    start_pkt = make_packet(START, 0)
    while True:
        s.sendto(start_pkt, dest)
        s.settimeout(TIMEOUT)
        try:
            raw, _ = s.recvfrom(2048)
        except socket.timeout:
            continue
        parsed = parse_packet(raw)
        if parsed and parsed[0] == ACK and parsed[1] == 1:
            break
    s.settimeout(0.05)
    try:
        while True:
            s.recvfrom(2048)
    except socket.timeout:
        pass
    base = 1
    next_seq = 1
    acked = set()
    timer_start = time.time()
    while base <= total:
        while next_seq < base + window_size and next_seq <= total:
            s.sendto(packets[next_seq], dest)
            next_seq += 1

        remaining = TIMEOUT - (time.time() - timer_start)
        if remaining <= 0:
            for seq in range(base, next_seq):
                if seq not in acked:
                    s.sendto(packets[seq], dest)
            timer_start = time.time()
            continue

        s.settimeout(remaining)
        try:
            raw, _ = s.recvfrom(2048)
        except socket.timeout:
            continue
        parsed = parse_packet(raw)
        if parsed is None or parsed[0] != ACK:
            continue
        ack = parsed[1]
        if base <= ack < next_seq:
            acked.add(ack)
            if base in acked:
                while base in acked:
                    acked.discard(base)
                    base += 1
                timer_start = time.time()
    end_seq = total + 1
    end_pkt = make_packet(END, end_seq)
    deadline = time.time() + TIMEOUT
    s.sendto(end_pkt, dest)
    last_send = time.time()
    while True:
        now = time.time()
        if now >= deadline:
            break
        if now - last_send >= 0.1:
            s.sendto(end_pkt, dest)
            last_send = now
        s.settimeout(max(0.001, min(0.1, deadline - now)))
        try:
            raw, _ = s.recvfrom(2048)
        except socket.timeout:
            continue
        parsed = parse_packet(raw)
        if parsed and parsed[0] == ACK and parsed[1] == end_seq:
            break
        
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip", help="The IP address of the host that receiver is running on")
    parser.add_argument("receiver_port", type=int, help="The port number on which receiver is listening")
    parser.add_argument("window_size", type=int, help="Maximum number of outstanding packets")
    args = parser.parse_args()
    sender(args.receiver_ip, args.receiver_port, args.window_size)
if __name__ == "__main__":
    main()