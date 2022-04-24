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

        while current_packet < number_of_frames:
            # sender
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

            # receiver
            # TODO
            #   if acks miss
            #   frame 1 ack misses
            #   frame 2 ack misses
            #   frame 1 arrives
            #   cannot result in nak
            while not sender_queue.empty():
                packet = sender_queue.queue[0]
                if packet.sequence_number == current_ack % max_sequence_number:
                    sender_queue.get()
                    global_packet_counter += 1
                    current_ack += 1
                    packet.ack = "ACK"
                    most_cumulative_ack = packet

                    # searches for possible next packages ready to ack in queue
                    # if any are found, will advance as if acking packages but only save the last ack to be sent
                    while not packets_in_waiting.empty():
                        packet = packets_in_waiting.queue[0]

                        if packet.sequence_number == current_ack % max_sequence_number:
                            packets_in_waiting.get()
                            current_ack += 1
                            packet.ack = "ACK"
                            most_cumulative_ack = packet
                            continue
                        break

                    if global_packet_counter in lost_packets:
                        print(f"B --x A : Ack {current_ack % max_sequence_number}")
                    else:
                        print(f"B -->> A : Ack {current_ack % max_sequence_number}")
                        receiver_queue.put(most_cumulative_ack)
                    continue

                sender_queue.get()
                packets_in_waiting.put(packet)
                if global_packet_counter in lost_packets:
                    print(f"B --x A : NAK {current_ack % max_sequence_number}")
                else:
                    print(f"B -->> A : NAK {current_ack % max_sequence_number}")
                    receiver_queue.put(
                        Packet(payload=current_ack, sequence_number=current_ack % max_sequence_number, ack="NAK"))

            # check for acks
            while not receiver_queue.empty():
                ack: Packet = receiver_queue.get()
                if ack.ack == "ACK":
                    if ack.payload > current_packet:
                        current_packet = ack.payload
                    continue
                current_packet = ack.payload
                packets_to_resend.put(packets[ack.payload])

            # if any packets went unacked
            oldest_package = None
            for i in range(current_packet, next_packet_in_window):
                packets[i].time += 1
                if packets[i].time > packets[i].max_time:
                    if oldest_package is None:
                        oldest_package = i
                        continue
                    if packets[oldest_package].time < packets[i].time:
                        oldest_package = i

            if oldest_package is not None:
                if packets[oldest_package].timed_out and packets[oldest_package] not in packets_to_resend.queue:
                    print(f"Note over A : TIMEOUT ({oldest_package + 1})")
                    packets[oldest_package].time = 1
                    packets_to_resend.put(packets[oldest_package])
                else:
                    packets[oldest_package].timed_out = True

            # retransmit nack
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
print("\nend")
exit()
