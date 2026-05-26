# Got and modified from https://github.com/cispa/security-header-parsing/ to suit our needs.
import random
import unicodedata
from dataclasses import dataclass

@dataclass(frozen=True)
class Mutation:
    apply: callable
    metadata: list

class Mutator:
    # All ASCII chars (+ some more) as leading, trailing, and middle char
    ascii_chars = [char for char in map(chr, range(128))]
    other_chars = ["  ", "\u00A0", "\uFF0C"] # Double space, non-breaking space, full-width comma
    # Replace some chars with others
    chars_to_replace = [";", ",", ":", "=", "'", '"', "-", "_"]
    # Replace each of the above with all of the below
    replace_with_chars = [
        "", " ", ";", ",", ":", "=", "-", "_",
        "'", '"', "`", "´",
        '\u2018',  # Left Single Quotation Mark
        '\u2019',  # Right Single Quotation Mark
        '\u201A',  # Single Low-9 Quotation Mark
        '\u201B',  # Single High-Reversed-9 Quotation Mark
        '\u201C',  # Left Double Quotation Mark
        '\u201D',  # Right Double Quotation Mark
        '\u201E',  # Double Low-9 Quotation Mark
        '\u201F',  # Double High-Reversed-9 Quotation Mark
    ]
    basic_whitespaces = [" ", "\n", "\r", "\t", "\v", "\f"] # v,f: HTTP / legacy header whitespace (important for security)
    CONTROL_NAMES = {
        '\0': 'NULL',
        '\u0001': "START OF HEADING",
        '\u0002': "START OF TEXT",
        '\u0003': "END OF TEXT",
        '\u0004': "END OF TRANSMISSION",
        '\u0005': "ENQUIRY",
        '\u0006': "ACKNOWLEDGE",
        '\u0007': "BELL",
        '\u0008': "BACKSPACE",
        '\t': 'HORIZONTAL TAB',
        '\n': 'NEW LINE',
        '\v': 'VERTICAL TAB',
        '\f': 'FORM FEED',
        '\r': 'CARRIAGE RETURN',
        '\u000e': 'SHIFT OUT',
        '\u000f': 'SHIFT IN',
        '\u0010': 'DATA LINK ESCAPE',
        '\u0011': 'DEVICE CONTROL ONE',
        '\u0012': 'DEVICE CONTROL TWO',
        '\u0013': 'DEVICE CONTROL THREE',
        '\u0014': 'DEVICE CONTROL FOUR',
        '\u0015': 'NEGATIVE ACKNOWLEDGE',
        '\u0016': 'SYNCHRONOUS IDLE',
        '\u0017': 'END OF TRANSMISSION BLOCK',
        '\u0018': 'CANCEL',
        '\u0019': 'END OF MEDIUM',
        '\u001a': 'SUBSTITUTE',
        '\u001b': 'ESCAPE',
        '\u001c': 'FILE SEPARATOR',
        '\u001d': 'GROUP SEPARATOR',
        '\u001e': 'RECORD SEPARATOR',
        '\u001f': 'UNIT SEPARATOR',
        ' ': 'SPACE',
        '\u007f': 'DELETE'
    }
    CONTROL_OTHER = {
        "": 'EMPTY STRING',
        "  ": 'DOUBLE SPACE'
    }
    
    def run_all(self, values, header_name_mutation=False):
        lead_seqs, trail_seqs, middle_seqs = self.populate_with_chars(chars = self.ascii_chars + self.other_chars)
        replace_funcs = self.replace_characters(chars_to_replace=self.chars_to_replace, replace_with_chars=self.replace_with_chars)
        general_mutations = [
            self.all_upper,
            self.all_lower,
            self.randomize_casing,
            self.leadtrail_space,
            self.in_double_quotes,
            self.in_single_quotes,
            self.remove_whitespace,
            self.double_spaces,
            self.space_to_tab,
            *lead_seqs,
            *trail_seqs,
            *middle_seqs,
            *replace_funcs,
        ]
        return self._run(values=values, mutation_list=general_mutations, header_name_mutation=header_name_mutation)
    
    def run_basic(self, values, header_name_mutation=False):
        # lead_seqs, trail_seqs, middle_seqs = self.populate_with_chars(chars=self.basic_whitespaces)
        basic_mutations = [
            # self.all_upper,
            self.all_lower,
            self.randomize_casing,
            self.leadtrail_space,
            # *lead_seqs,
            # *trail_seqs,
            # *middle_seqs
        ]
        return self._run(values=values, mutation_list=basic_mutations, header_name_mutation=header_name_mutation)
    
    def _run(self, values, mutation_list, header_name_mutation):
        current_mutated_values = {}
        for value in values:
            mutated_values = self.mutate(value=value, mutation_list=mutation_list,header_name_mutation=header_name_mutation)
            current_mutated_values.update(mutated_values)
        return current_mutated_values

    def mutate(self, value, mutation_list, header_name_mutation):
        mutated_values = {}
        for mutation in mutation_list:
            mutation_obj = mutation if type(mutation) is Mutation else mutation() # else means it is a method
            mutated_value = mutation_obj.apply(value)
            if mutated_value == value:
                continue # didn't change it
            mutation_obj.metadata['mutation_in'] = "mechanism_value" if header_name_mutation is False else "header_name"
            # mutation_obj.metadata['org_value'] = value
            mutated_values[mutated_value] = mutation_obj.metadata
        return mutated_values
    
    # Mutation methods:
    def populate_with_chars(self, chars):
        lead_seqs = []
        trail_seqs = []
        middle_seqs = []
        for seq in chars:
            lead_seqs.append(
                Mutation(
                    apply=lambda x, s=seq: s + x,
                    metadata={
                        "mutation": True,
                        "mutation_type": "populate_with_chars",
                        "populate_char_position": "leading",
                        "char": self.get_char_name_or_code(seq)
                    }
                )
            )
            trail_seqs.append(
                Mutation(
                    apply=lambda x, s=seq: x + s,
                    metadata={
                        "mutation": True,
                        "mutation_type": "populate_with_chars",
                        "populate_char_position": "trailing",
                        "char": self.get_char_name_or_code(seq)
                    }
                )
            )
            middle_seqs.append(
                Mutation(
                    apply=lambda x, s=seq: self.insert_char_middle(x, s),
                    metadata={
                        "mutation": True,
                        "mutation_type": "populate_with_chars",
                        "populate_char_position": "middle",
                        "char": self.get_char_name_or_code(seq)
                    }
                )
            )
        return lead_seqs, trail_seqs, middle_seqs

    def replace_characters(self, chars_to_replace, replace_with_chars):
        replace_funcs = []
        for char in chars_to_replace:
            for rp in replace_with_chars:
                if rp == char:
                    continue
                replace_funcs.append(
                    Mutation(
                        apply=lambda x, c1=char, c2=rp: x.replace(c1, c2),
                        metadata={
                            "mutation": True,
                            "mutation_type": "replace_characters",
                            "replace_from": self.get_char_name_or_code(char),
                            "replace_to": self.get_char_name_or_code(rp)
                        }
                    )
                )
        return replace_funcs

    def randomize_casing(self, seed=42):
        def apply(input_string):
            """Randomize the casing of a string (fixed with a seed)."""
            random.seed(seed)
            return ''.join(random.choice([c.upper(), c.lower()]) for c in input_string)
        return Mutation(
            apply=apply,
            metadata={
                "mutation": True,
                "mutation_type": "case_mutation",
                "case": "random"
            }
        )
    
    def all_upper(self):
        return Mutation(
            apply=lambda x: x.upper(),
            metadata={
                "mutation": True,
                "mutation_type": "case_mutation",
                "case": "all_upper"
            }
        )

    def all_lower(self):
        return Mutation(
            apply=lambda x: x.lower(),
            metadata={
                "mutation": True,
                "mutation_type": "case_mutation",
                "case": "all_lower"
            }
        )

    def leadtrail_space(self):
        add_c = " "
        return Mutation(
            apply=lambda x: add_c + x + add_c,
            metadata={
                "mutation": True,
                "mutation_type": "populate_with_chars",
                "populate_char_position": ["leading","trailing"],
                "char": self.get_char_name_or_code(add_c)
            }
        )
    
    def in_double_quotes(self):
        add_c = '"'
        return Mutation(
            apply=lambda x: add_c + x + add_c,
            metadata={
                "mutation": True,
                "mutation_type": "populate_with_chars",
                "populate_char_position": ["leading","trailing"],
                "char": self.get_char_name_or_code(add_c)
            }
        )
    
    def in_single_quotes(self):
        add_c = "'"
        return Mutation(
            apply=lambda x: add_c + x + add_c,
            metadata={
                "mutation": True,
                "mutation_type": "populate_with_chars",
                "populate_char_position": ["leading","trailing"],
                "char": self.get_char_name_or_code(add_c)
            }
        )

    def remove_whitespace(self):
        c_from = " "
        c_to = ""
        return Mutation(
            apply=lambda x: x.replace(c_from, c_to),
            metadata={
                "mutation": True,
                "mutation_type": "replace_characters",
                "replace_from": self.get_char_name_or_code(c_from),
                "replace_to": self.get_char_name_or_code(c_to)
            }
        )
    
    def double_spaces(self):
        c_from = " "
        c_to = "  "
        return Mutation(
            apply=lambda x: x.replace(c_from, c_to),
            metadata={
                "mutation": True,
                "mutation_type": "replace_characters",
                "replace_from": self.get_char_name_or_code(c_from),
                "replace_to": self.get_char_name_or_code(c_to)
            }
        )
    
    def space_to_tab(self):
        c_from = " "
        c_to = "\t"
        return Mutation(
            apply=lambda x: x.replace(c_from, c_to),
            metadata={
                "mutation": True,
                "mutation_type": "replace_characters",
                "replace_from": self.get_char_name_or_code(c_from),
                "replace_to": self.get_char_name_or_code(c_to)
            }
        )
    
    # helpers:
    def insert_char_middle(self, input_string, char):
        """Insert a char in the middle of a string."""
        middle_index = len(input_string) // 2
        return input_string[:middle_index] + char + input_string[middle_index:]
    
    def get_char_name_or_code(self, char): # better get name or ascii code as characters may not be visible in the report or cause problems if saved as is ! 
        if char in self.CONTROL_OTHER:
            return self.CONTROL_OTHER[char]
        fallback = "Name not defined"
        try_completer=False
        try:
            name = unicodedata.name(char, fallback) # try getting name
            if name == fallback:
                try_completer=True
        except Exception as e:
            try_completer=True
        if try_completer is True:
            name = self.unicode_name_completer(char=char) # if couldn't get it, try to find it by ourselves
        return name

    def unicode_name_completer(self, char):
        # return self.CONTROL_NAMES.get(char, char) # last resort return character as is!
        return self.CONTROL_NAMES.get(char, f"U+{ord(char):04X}")
