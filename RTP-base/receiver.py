import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum

START, END, DATA, ACK = 0, 1, 2, 3
HEADER_LEN = 16

def make_packet(pkt_type, seq_num, data=b""):
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

def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    out = sys.stdout.buffer
    connected = False
    expected = 1
    buffer = {}
    while True:
        raw, address = s.recvfrom(2048)
        parsed = parse_packet(raw)
        if parsed is None:
            continue
        pkt_type, seq_num, data = parsed
        if pkt_type == START:
            if connected:
                continue
            connected = True
            expected = 1
            buffer = {}
            s.sendto(make_packet(ACK, 1), address)
        elif not connected:
            continue
        elif pkt_type == DATA:
            if seq_num >= expected + window_size:
                continue
            if seq_num >= expected:
                buffer[seq_num] = data
                while expected in buffer:
                    out.write(buffer.pop(expected))
                    expected += 1
            s.sendto(make_packet(ACK, expected), address)
        elif pkt_type == END:
            s.sendto(make_packet(ACK, seq_num), address)
            break
    out.flush()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip", help="The IP address of the host that receiver is running on")
    parser.add_argument("receiver_port", type=int, help="The port number on which receiver is listening")
    parser.add_argument("window_size", type=int, help="Maximum number of outstanding packets")
    args = parser.parse_args()
    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
