import sys
import threading
from enum import Enum
from queue import Queue, Empty
from typing import List


class ProtocolsEnum(Enum):
    STOP_AND_WAIT_ARQ = "saw"
    GO_BACK_N_ARQ = "gbn"
    SELECTIVE_REPEAT_ARQ = "sr"


def flow_control_simulation(protocol: ProtocolsEnum, sequence_of_bits: int, number_of_frames: int,
                            lost_packets: List[int]):
    if protocol == ProtocolsEnum.STOP_AND_WAIT_ARQ:
        sequence_of_bits = 1

    receiver_queue = Queue(maxsize=1)
    receiver_channel_queue = Queue(maxsize=1)

    sender_queue = Queue(maxsize=1)
    sender_channel_queue = Queue(maxsize=1)

    quit_signal = Queue(maxsize=1)

    packet_counter_updater_queue = Queue(maxsize=1)

    packages = Queue(maxsize=number_of_frames)
    for i in range(1, number_of_frames + 1):
        packages.put(i)

    def saw_sender():
        sequence_number = 0
        while not packages.empty():
            # Save package in case it needs to be resent
            payload = packages.get()
            acknowledged = False
            retransmission = False
            while not acknowledged:
                packet = {
                    "sequence_number": sequence_number,
                    "payload": payload,
                    "retransmission": retransmission
                }
                sender_channel_queue.put(packet)
                try:
                    acknowledged = sender_queue.get(block=True, timeout=0.3)
                    sequence_number = int(not sequence_number)
                except Empty:
                    retransmission = True
                    continue
        quit_signal.put(1)

    def saw_receiver():
        # Receiver never stops listening
        expected_sequence_number = 0
        while True:
            packet = receiver_queue.get(block=True)
            sequence_number = int(packet["sequence_number"])
            if sequence_number == expected_sequence_number:
                expected_sequence_number = int(not expected_sequence_number)
            receiver_channel_queue.put(str(expected_sequence_number))

    def sender_listen_and_forward():
        while True:
            packet = sender_channel_queue.get(block=True)
            packet_counter_updater_queue.put(1, block=True)
            if packet_counter in lost_packets:
                print(f"A -x B: ({packet['payload']}) Frame {packet['sequence_number']}")
                print(f"Note over A : TIMEOUT ({packet['payload']})")
                continue
            print(
                f"A ->> B: ({packet['payload']}) Frame {packet['sequence_number']} {'[RET]' if packet['retransmission'] else ''}")
            receiver_queue.put(packet)

    def receiver_listen_and_forward():
        while True:
            packet = receiver_channel_queue.get(block=True)
            packet_counter_updater_queue.put(1, block=True)
            if packet_counter in lost_packets:
                continue
            print(f"B -->> A: Ack {packet}")
            sender_queue.put(packet)

    # We're using a packet_counter_updater to avoid any concurrency problems that might arise
    def packet_counter_updater():
        global packet_counter
        while True:
            if not packet_counter_updater_queue.empty():
                packet_counter += 1
                packet_counter_updater_queue.get(block=True)

    protocol_functions_dictionary = {
        ProtocolsEnum.STOP_AND_WAIT_ARQ: {"sender_function": saw_sender, "receiver_function": saw_receiver}
    }

    protocol_functions = protocol_functions_dictionary.get(protocol)

    threading.Thread(target=protocol_functions["sender_function"]).start()
    threading.Thread(target=protocol_functions["receiver_function"]).start()
    threading.Thread(target=sender_listen_and_forward).start()
    threading.Thread(target=receiver_listen_and_forward).start()
    threading.Thread(target=packet_counter_updater).start()
    quit_signal.get(block=True)


arguments = sys.argv
if len(arguments) != 5:
    print("python flowctrlsim <protocol> <seqbits> <num_frames> <lost_pkts>")
    exit()

arg_protocol = ProtocolsEnum(arguments[1])
arg_sequence_of_bits = int(arguments[2])
arg_number_of_frames = int(arguments[3])
arg_lost_packets = [int(i) for i in arguments[4].split(',')]

# We'll be keeping count of a global packet counter so that we can simulate loss of both frames and ACKs
# Packet counter will increase on failure as well, so packet_counter will not be synchronized to the frame number
packet_counter = 1

flow_control_simulation(protocol=arg_protocol, sequence_of_bits=arg_sequence_of_bits,
                        number_of_frames=arg_number_of_frames,
                        lost_packets=arg_lost_packets)
print("\nend")
exit()
