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
    sender_queue = Queue(maxsize=1)
    channel_queue = Queue(maxsize=1)
    quit_signal = Queue(maxsize=1)

    packages = Queue(maxsize=number_of_frames)
    for i in range(1, number_of_frames):
        packages.put(i)

    def saw_sender():
        sequence_number = 0
        while not packages.empty():
            # Save package in case it needs to be resent
            payload = packages.get()
            packet = str(sequence_number) + str(payload)
            ack = False
            while not ack:
                print(
                    f"Envio do frame {payload} com seq {sequence_number}: A ->> B: ({payload}) Frame {sequence_number}")
                channel_queue.put(packet)
                try:
                    ack = sender_queue.get(block=True, timeout=2)
                    sequence_number = int(not sequence_number)
                except Empty:
                    print(
                        f"Timeout para receber ack do frame {payload}: Note over A : TIMEOUT ({payload})")
                    continue
        quit_signal.put(1)

    def saw_receiver():
        # Receiver never stops listening
        expected_sequence_number = 0
        while True:
            packet = receiver_queue.get(block=True)
            sequence_number = int(packet[0])
            ack = str(sequence_number) + "1"
            if sequence_number == expected_sequence_number:
                expected_sequence_number = int(not expected_sequence_number)
            print(f"ACK do frame {sequence_number}: B -->> A: ACK {sequence_number + 1}")
            channel_queue.put(ack)

    def listen_and_forward():
        packet_counter = 1
        packet_lost = False
        while True:
            packet = channel_queue.get(block=True)
            # Packet is always sent
            receiver_queue.put(packet)
            ack = channel_queue.get(block=True)
            # Packet loss will be simulated on ACKs
            if packet_counter in lost_packets:
                if not packet_lost:
                    packet_lost = True
                    continue
            sender_queue.put(ack)
            packet_counter += 1
            packet_lost = False

    protocol_functions_dictionary = {
        ProtocolsEnum.STOP_AND_WAIT_ARQ: {"sender_function": saw_sender, "receiver_function": saw_receiver}
    }

    protocol_funcions = protocol_functions_dictionary.get(protocol)

    threading.Thread(target=protocol_funcions["sender_function"]).start()
    threading.Thread(target=protocol_funcions["receiver_function"]).start()
    threading.Thread(target=listen_and_forward).start()
    quit_signal.get(block=True)
    print("quit received, ending")


arguments = sys.argv
if len(arguments) != 5:
    print("python flowctrlsim <protocol> <seqbits> <num_frames> <lost_pkts>")
    exit()

arg_protocol = ProtocolsEnum(arguments[1])
arg_sequence_of_bits = int(arguments[2])
arg_number_of_frames = int(arguments[3])
arg_lost_packets = [int(i) for i in arguments[4].split(',')]

flow_control_simulation(protocol=arg_protocol, sequence_of_bits=arg_sequence_of_bits,
                        number_of_frames=arg_number_of_frames,
                        lost_packets=arg_lost_packets)
print("end")
exit()
