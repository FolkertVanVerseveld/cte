from typing import List, Tuple
from text_block import TextBlock


class PieceTable:
    """
    Text file data structure consisting of the original file together with
    so-called "edit-blocks" (see the TextBlock class), for which a table is
    used to couple these seperate blocks into one single file.

    Edit-blocks can can be created on top of the original file and locked, such
    that no other edit-blocks can be created on top of them, until the
    edit-block is closed manually. Edit-blocks can thereafter be edited such,
    while the piece table makes sure the general structure stays intact.
    """
    def __init__(self, text) -> None:
        if isinstance(text, str):
            lines = text.splitlines(True)
        else:
            lines = text

        orig_piece = TextBlock(lines, False)
        self.blocks: Dict[TextBlock] = {0: orig_piece}
        self.table: List[List[int]] = [[0, 0, len(lines)]]

    def __len__(self) -> int:
        """
        Returns the length of the stitched file according to the piece table.
        """
        length: int = 0

        for i in range(len(self.table)):
            length += self.table[i][2]

        return length

    def __str__(self) -> str:
        fmt = "{:>10}"*4
        str_table = ""

        str_table += fmt.format("Block ID", "Start", "Length", "Open") + "\n"
        for item in self.table:
            str_table += fmt.format(item[0], item[1], item[2],
                                    self.blocks[item[0]].is_open()) + "\n"

        return str_table

    def line_to_table_index(self, line: int) -> Tuple[int, int]:
        """
        Returns the corresponding piece index and piece offset
        for a given file line.
        """
        piece_start: int = 0
        i: int
        for i in range(len(self.table)):
            piece_length: int = self.table[i][2]

            if line >= piece_start and line < piece_start + piece_length:
                return i, line - piece_start

            piece_start += block_length
        raise ValueError("Invalid line number")

    def get_piece_start(self, piece_index: int) -> int:
        """
        Returns the line at which the given piece (table index) begins within
        the stitched file.
        """
        line: int = 0
        for i in range(piece_index):
            line += self.table[i][2]

        return line

    def get_piece_range(self, start: int, length: int) -> Tuple[int, int]:
        """
        Returns a range of pieces which cover the given line range, in the
        form '(start_pieces, end_piece)'.
        """
        first, offset = self.line_to_table_index(start)
        length_rem: int = length - (self.table[first][2] - offset)
        last_off: int = 1

        while length_rem > 0 and first + last_off < len(self.table):
            length_rem -= self.table[first + last_off][2]
            last_off += 1

        return first, first + last_off - 1

    def get_lines(self, start: int, length: int) -> List[str]:
        """
        Returns a list with the requested lines assembled
        from the piece present in the piece table.

        When length is -1, returns until the last line.
        """
        if length < 0:
            length = len(self)

        lines: List[str] = []
        length_rem: int = length
        index, offset = self.line_to_table_index(start)
        first, last = self.get_piece_range(start, length)

        for i in range(first, last + 1):
            tab_ent = self.table[i]
            block = self.blocks[tab_ent[0]]

            line_s = tab_ent[1]
            line_c = tab_ent[2]

            if i == first:
                line_s += offset
                line_c -= offset

            lines.extend(block.get_lines(line_s, min(length_rem, line_c)))

            length_rem -= tab_ent[2]

        return lines

    def get_locked_block_info(self, block_id: str) -> Tuple[int, int]:
        """
        If the given block is locked, returns the current block length
        and starting location within the file.
        Unlocked block_id's return wrong results.
        """
        cur_pos = 0
        for piece in self.table:
            if piece[0] is block_id:
                return (cur_pos, piece[2])
            else:
                cur_pos += piece[2]
        return None

    def stitch(self) -> List[str]:
        """
        Returns the new stitched file according to the piece table.
        """
        stitched_file: List[str] = []
        position = 0
        for block_i, start, length in self.table:
            position += length

            stitched_file.extend(self.blocks[block_i].get_lines(start, length))

        return stitched_file

    def remove_closed_blocks(self) -> List[str]:
        """
        Stitches the file and removes closed edit-blocks. Then updates all
        open edit-blocks.

        Use when saving to disk.
        """
        stitched_file = self.stitch()
        self.blocks[0] = TextBlock(stitched_file)
        # TODO: update open block indices & table

        # Update the table section lengths and starting positions
        cur_pos = 0
        last_open_index = 0
        for i, section in enumerate(self.table):
            if self.blocks[section[0]].is_open():
                last_open_index = i + 1
            else:
                self.table[last_orig_index][2] += section[2]

                if i is last_open_index:
                    section = [0, cur_pos, section[2]]
                else:
                    # '-1' signal that the section is to be removed.
                    section[0] = -1

            cur_pos += section[2]

        self.table = [s for s in self.table if not s[0] is -1]

        # Remove the closed blocks from memory
        for block_id in self.blocks.keys():
            if not self.blocks[block_id].is_open():
                del self.blocks[block_id]

        return stitched_file

    def open_block(self, start: int, length: int) -> int:
        """
        Opens a new block in the piece table starting at the given
        line number with the given length.

        Raises a ValueError when trying to open a locked area, or when outside
        of file boundaries.
        """
        # Check if block creation is allowed
        range_start, range_end = self.get_piece_range(start, length)
        for piece_index in range(range_start, range_end + 1):
            if self.blocks[self.table[piece_index][0]].is_open() is True:
                raise ValueError("Illegal block request")

        if start + length > len(self):
            raise ValueError("Illegal block request")

        # Create the new TextBlock object
        block_lines: List[str] = self.get_lines(start, length)

        new_block: TextBlock = TextBlock(block_lines)
        block_id = max(self.blocks.keys()) + 1
        self.blocks[block_id] = new_block

        # Find and shrink previous containing block
        index, offset = self.line_to_table_index(start)
        prev_len: int = self.table[index][2]
        self.table[index][2] = offset

        # Insert the new block in the table
        self.table.insert(index + 1, [len(self.blocks) - 1, 0, length])

        # Update the rest of the table
        rem: int = prev_len - (offset + length)
        if rem > 0:
            # Insert remainder of previous containing block after new block
            n_start = self.table[index][1] + offset + length

            self.table.insert(index + 2, [self.table[index][0], n_start, rem])
        else:
            # Cut or shrink the next couple blocks to make space
            length_rem: int = -1 * rem
            cur_piece_index: int = index + 2

            while length_rem > 0 and len(self.table) > cur_piece_index:
                piece_len: int = self.table[cur_piece_index][2]

                if length_rem > piece_len:
                    length_rem -= piece_len
                    del self.table[cur_piece_index]
                else:
                    self.table[cur_piece_index][1] += length_rem
                    self.table[cur_piece_index][2] -= length_rem

                    break

        return block_id

    def close_block(self, block_id: int) -> None:
        """
        Closes the block with the corresponsing index.

        The block is kept within the piece table but should not be written to
        anymore.
        """
        self.blocks[block_id].close()