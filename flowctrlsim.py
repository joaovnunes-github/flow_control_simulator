import sys
from enum import Enum
from queue import Queue
from typing import List


class ProtocolsEnum(Enum):
    STOP_AND_WAIT_ARQ = "saw"
    GO_BACK_N_ARQ = "gbn"
    SELECTIVE_REPEAT_ARQ = "sr"


class Packet:
    payload: int
    retransmission: bool
    sequence_number: int
    time: int = 0
    max_time: int = 2
    ack: str = None
    timed_out = False

    def __init__(
            self, payload: int = 1, retransmission: bool = False, sequence_number: int = 0, time: int = 0,
            max_time: int = 2,
            ack: str = None
    ):
        self.payload: int = payload
        self.retransmission: bool = retransmission
        self.sequence_number: int = sequence_number
        self.time: int = time
        self.ack = ack
        self.max_time = max_time


def flow_control_simulation(
        protocol: ProtocolsEnum,
        sequence_of_bits: int,
        number_of_frames: int,
        lost_packets: List[int],
):
    max_sequence_number = 2 if protocol == ProtocolsEnum.STOP_AND_WAIT_ARQ else (2 ** sequence_of_bits)
    if protocol == ProtocolsEnum.SELECTIVE_REPEAT_ARQ:
        sequence_of_bits -= 1
    window_size = 2 if protocol == ProtocolsEnum.STOP_AND_WAIT_ARQ else (2 ** sequence_of_bits)

    packets = []
    # create all packets for sending
    for frame_number in range(number_of_frames):
        packets.append(
            Packet(
                payload=frame_number + 1,
                retransmission=False,
                sequence_number=frame_number % max_sequence_number,
            )
        )

    def saw():
        global global_packet_counter
        current_packet = 0

        while current_packet < number_of_frames:
            global_packet_counter += 1
            # sender
            packet = packets[current_packet]
            if global_packet_counter in lost_packets:
                packet.retransmission = True
                print(f"A -x B : ({packet.payload}) Frame {packet.sequence_number}")
                print(f"Note over A : TIMEOUT ({packet.payload})")
                continue
            print(
                f"A ->> B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}"
            )

            global_packet_counter += 1
            # receiver
            if global_packet_counter in lost_packets:
                packet.retransmission = True
                print(f"B --x A : Ack {packet.sequence_number % max_sequence_number}")
                continue
            print(f"B -->> A : Ack {packet.sequence_number % max_sequence_number}")
            current_packet += 1

    def gbn():
        global global_packet_counter
        current_packet = 0
        next_packet_in_window = 0

        sender_queue = Queue()
        receiver_queue = Queue()
        while current_packet < number_of_frames:

            # check for acks
            while not receiver_queue.empty():
                ack = receiver_queue.get()
                if ack > current_packet:
                    current_packet = ack

            # if any packets went unacked
            for i in range(current_packet, next_packet_in_window):
                packets[i].time += 1
                if packets[i].time > 2:
                    if current_packet < next_packet_in_window:
                        print(f"Note over A : TIMEOUT ({current_packet + 1})")
                    next_packet_in_window = current_packet

            # sender
            while (
                    not next_packet_in_window - current_packet >= max_sequence_number - 1
                    and not next_packet_in_window > frame_number
            ):
                global_packet_counter += 1
                packet = packets[next_packet_in_window]
                if global_packet_counter in lost_packets:
                    print(
                        f"A -x B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}")
                else:
                    print(
                        f"A ->> B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}"
                    )
                    sender_queue.put(packet)
                packet.time = 1
                packet.retransmission = True
                next_packet_in_window += 1

            # receiver
            ack = current_packet
            while not sender_queue.empty():
                packet = sender_queue.get()
                if packet.sequence_number == ack % max_sequence_number:
                    global_packet_counter += 1
                    ack += 1
                    if global_packet_counter in lost_packets:
                        print(f"B --x A : Ack {ack % max_sequence_number}")
                    else:
                        print(f"B -->> A : Ack {ack % max_sequence_number}")
                        receiver_queue.put(ack)

    def sr():
        global global_packet_counter
        current_packet = 0
        current_ack = 0
        next_packet_in_window = 0

        sender_queue = Queue()
        receiver_queue = Queue()
        packets_to_resend = Queue()
        packets_in_waiting = Queue()
        ack_buffer = Queue()
        nack_buffer = {}

        while current_packet < number_of_frames:
            # We send the packages
            while (
                    not next_packet_in_window - current_packet >= window_size
                    and not next_packet_in_window > frame_number
            ):
                global_packet_counter += 1
                packet = packets[next_packet_in_window]
                if global_packet_counter in lost_packets:
                    print(
                        f"A -x B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}")
                else:
                    print(
                        f"A ->> B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}"
                    )
                    sender_queue.put(packet)
                packet.time = 1
                packet.max_time = 2
                packet.retransmission = True
                next_packet_in_window += 1

            # We receive the packages
            while not sender_queue.empty():
                packet = sender_queue.queue[0]
                # Check if this is the expected package
                if packet.sequence_number == current_ack % max_sequence_number:
                    # If this package had been NACKed, we remove it from the NACK buffer
                    if packet.sequence_number in nack_buffer.keys():
                        nack_buffer.pop(packet.sequence_number)

                    sender_queue.get()
                    global_packet_counter += 1

                    current_ack += 1
                    packet.ack = "ACK"
                    most_cumulative_ack = packet

                    # We add the package to the ACK buffer
                    if ack_buffer.qsize() <= window_size:
                        ack_buffer.put(packet)
                    else:
                        ack_buffer.get()
                        ack_buffer.put(packet)

                    # searches for possible next packages ready to ack in queue
                    # if any are found, will advance as if acking packages but only save the last ack to be sent
                    while not packets_in_waiting.empty():
                        packet = packets_in_waiting.queue[0]

                        if packet.sequence_number == current_ack % max_sequence_number:
                            if packet.sequence_number in nack_buffer.keys():
                                nack_buffer.pop(packet.sequence_number)

                            packets_in_waiting.get()
                            current_ack += 1
                            packet.ack = "ACK"
                            most_cumulative_ack = packet

                            # adding to buffer
                            if ack_buffer.qsize() <= window_size:
                                ack_buffer.put(packet)
                            else:
                                ack_buffer.get()
                                ack_buffer.put(packet)

                            continue
                        break

                    if global_packet_counter in lost_packets:
                        print(f"B --x A : Ack {current_ack % max_sequence_number}")
                    else:
                        print(f"B -->> A : Ack {current_ack % max_sequence_number}")
                        receiver_queue.put(most_cumulative_ack)
                    continue

                # In case we had already ACKED this package
                # We will resend our last (most cumulative) ACK
                elif packet.sequence_number in [buffered_packet.sequence_number
                                                for buffered_packet in ack_buffer.queue]:
                    sender_queue.get()
                    global_packet_counter += 1
                    if global_packet_counter in lost_packets:
                        print(f"B --x A : Ack {current_ack % max_sequence_number}")
                    else:
                        print(f"B -->> A : Ack {current_ack % max_sequence_number}")
                        receiver_queue.put(ack_buffer.queue[-1])
                    continue

                # If it is not the expected, nor a package we already ACKed
                # We send a NACK for the missing packages
                # And add this package to the waiting list
                else:
                    # If there are packages in waiting we check to see if extra NACKs need to be added
                    if not packets_in_waiting.empty():
                        i = packets_in_waiting.queue[-1].sequence_number
                        while i != packet.sequence_number:
                            if i not in [packet_in_waiting.sequence_number for packet_in_waiting in
                                         packets_in_waiting.queue]:
                                nack_buffer[i] = Packet(payload=i, sequence_number=i % max_sequence_number, ack="nak")
                            i = (i + 1) % max_sequence_number
                    # If there is no package in waiting we add a single NACK
                    else:
                        nack_buffer[current_ack % max_sequence_number] = Packet(payload=current_ack,
                                                                                sequence_number=current_ack % max_sequence_number,
                                                                                ack="NAK")

                    # After managing the buffers, we add the package to the waiting list and send NACKs
                    sender_queue.get()
                    packets_in_waiting.put(packet)
                    if sender_queue.empty():
                        for packet in nack_buffer.values():
                            global_packet_counter += 1
                            if global_packet_counter in lost_packets:
                                print(f"B --x A : NAK {packet.sequence_number}")
                            else:
                                print(f"B -->> A : NAK {packet.sequence_number}")
                                receiver_queue.put(packet)

            # After the receiver deals with the sent packages, we check the ACKs
            # Any packets not ACKed will be added to a resend list
            while not receiver_queue.empty():
                ack: Packet = receiver_queue.get()
                if ack.ack == "ACK":
                    if ack.payload > current_packet:
                        current_packet = ack.payload
                    continue
                current_packet = ack.payload
                packets_to_resend.put(packets[ack.payload])

            # After that, we manage the timers for packets that have not been ACKed/NACKed
            oldest_expired_package = None
            for i in range(current_packet, next_packet_in_window):
                packets[i].time += 1
                if packets[i].time > packets[i].max_time and packets[i] not in packets_to_resend.queue:
                    if oldest_expired_package is None:
                        oldest_expired_package = i
                        continue
                    if packets[oldest_expired_package].time < packets[i].time:
                        oldest_expired_package = i

            # If there are expired packages, we get the oldest one
            # If it is not in queue for resend we mark it as timed out
            # It will effectively time out by the next iteration
            if oldest_expired_package is not None:
                if packets[oldest_expired_package].timed_out:
                    print(f"Note over A : TIMEOUT ({oldest_expired_package + 1})")
                    packets[oldest_expired_package].time = 1
                    packets_to_resend.put(packets[oldest_expired_package])
                else:
                    packets[oldest_expired_package].timed_out = True

            # Before starting the next iteration, we resend packages marked for resending
            while not packets_to_resend.empty():
                global_packet_counter += 1
                packet = packets_to_resend.get()
                if global_packet_counter in lost_packets:
                    print(
                        f"A -x B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}")
                else:
                    print(
                        f"A ->> B : ({packet.payload}) Frame {packet.sequence_number} {'(RET)' if packet.retransmission else ''}"
                    )
                    sender_queue.put(packet)

    protocol_functions_dictionary = {
        ProtocolsEnum.STOP_AND_WAIT_ARQ: saw,
        ProtocolsEnum.GO_BACK_N_ARQ: gbn,
        ProtocolsEnum.SELECTIVE_REPEAT_ARQ: sr
    }

    protocol_functions_dictionary.get(protocol)()


arguments = sys.argv
if len(arguments) != 5:
    print("python flowctrlsim <protocol> <seqbits> <num_frames> <lost_pkts>")
    exit()

arg_protocol = ProtocolsEnum(arguments[1])
arg_sequence_of_bits = int(arguments[2])
arg_number_of_frames = int(arguments[3])
arg_lost_packets = [int(i) for i in arguments[4].split(",")]

# We'll be keeping count of a global packet counter so that we can simulate loss of both frames and ACKs
# Packet counter will increase on failure as well, so packet_counter will not be synchronized to the frame number
global_packet_counter = 0

flow_control_simulation(
    protocol=arg_protocol,
    sequence_of_bits=arg_sequence_of_bits,
    number_of_frames=arg_number_of_frames,
    lost_packets=arg_lost_packets,
)
exit()
