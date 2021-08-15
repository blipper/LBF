import re
import inflect

def find_all_occurences(sample_str, sub):
    start = 0
    while True:
        start = sample_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub) # use start += 1 to find overlapping matches

def normalize_fracs(string):
    substrs = string.split("\\frac")
    new_str = substrs[0]
    if len(substrs) > 1:
        substrs = substrs[1:]
        for substr in substrs:
            new_str += "\\frac"
            if substr[0] == "{":
                new_str += substr
            else:
                if substr[0] == " ":
                    substr = substr[1:] # \\frac 13 -> \\frac13 -> \\frac{1}{3}
                try:
                    assert len(substr) >= 2
                except:
                    return string
                a = substr[0]
                b = substr[1]
                if b != "{":
                    if len(substr) > 2:
                        post_substr = substr[2:]
                        new_str += "{" + a + "}{" + b + "}" + post_substr
                    else:
                        new_str += "{" + a + "}{" + b + "}"
                else:
                    if len(substr) > 2:
                        post_substr = substr[2:]
                        new_str += "{" + a + "}" + b + post_substr
                    else:
                        new_str += "{" + a + "}" + b
    string = new_str
    return string

def fix_frac(sample_str,original_string):
    new_str = sample_str
    left_brackets = list(find_all_occurences(new_str, '{'))
    right_brackets = list(find_all_occurences(new_str, '}'))
    fracs = list(find_all_occurences(new_str, '\\frac'))
    for frac_idx in range(len(fracs)):
        # Assuming no nested sqrts
        # Remove occurence of "\\frac"
        occurence = fracs[frac_idx]
        new_str = new_str[:occurence] + new_str[occurence+5:] 
        left_brackets = [x - 5 for x in left_brackets] # Update { bracket indices
        right_brackets = [x - 5 for x in right_brackets] # Update } bracket indices
        fracs = [x - 5 for x in fracs] # Update fracs bracket indices

        # Replace the first "{" corresponding to this fraction 
        new_str = new_str[:occurence] + "(" + new_str[occurence + 1:]

        # Replace the first "}" corresponding to this fraction, add the division operator
        right_brackets_relative = [x - occurence for x in right_brackets]
        next_right_bracket_idx = right_brackets_relative.index(min([i for i in right_brackets_relative if i > 0]))
        next_right_bracket = right_brackets[next_right_bracket_idx]
        new_str = new_str[:next_right_bracket] + ")/" + new_str[next_right_bracket + 1:]
        left_brackets = [x +1 for x in left_brackets] # Update { bracket indices
        right_brackets = [x +1 for x in right_brackets] # Update } bracket indices
        fracs = [x +1 for x in fracs] # Update fracs bracket indices

        # Replace the second "{" corresponding to this fraction 
        next_left_bracket = next_right_bracket + 2
        new_str = new_str[:next_left_bracket] + "(" + new_str[next_left_bracket + 1:]

        # Replace the second "}" corresponding to this fraction 
        right_brackets_relative = [x - next_left_bracket for x in right_brackets]
        try: 
            next_right_bracket_idx = right_brackets_relative.index(min([i for i in right_brackets_relative if i > 0]))
        except:
            print("FAILED FIX FRAC")
            print("Original String: " + original_string)
            print("Input String: " + sample_str)
            print("Updated String: " + new_str)
            print("rb relative" + str(right_brackets_relative))
            return new_str
        next_right_bracket = right_brackets[next_right_bracket_idx]
        new_str = new_str[:next_right_bracket] + ")" + new_str[next_right_bracket + 1:]

    return new_str

def fix_a_slash_b(string):
    if len(string.split("/")) != 2:
        return string
    a = string.split("/")[0]
    b = string.split("/")[1]
    try:
        a = int(a)
        b = int(b)
        assert string == "{}/{}".format(a, b)
        new_string = "\\frac{" + str(a) + "}{" + str(b) + "}"
        return new_string
    except:
        return string

def remove_right_units(string):
    # "\\text{ " only ever occurs (at least in the val set) when describing units
    if "\\text{ " in string:
        splits = string.split("\\text{ ")
        print(splits)
        assert len(splits) == 2
        return splits[0]
    else:
        return string

def order(string):
    if "(" in string or ")" in string or "[" in string or "]" in string or ", " not in string:
        return string

    # otherwise, split by "," and sort
    # ASSUMES commas have been removed from number representation (and spaces have been removed)
    splits = string.split(", ")
    splits = sorted(splits)
    new_str = ""
    for split in splits:
        new_str += split + ", "
    new_str = new_str[:-2]  # remove last ","
    try:
        assert new_str[-2:] != ", "  # for testing
    except:
        return string
    return new_str

def normalize_sqrt(string):
    if "\\sqrt" not in string:
        return string
    splits = string.split("\\sqrt")
    new_string = splits[0] 
    for split in splits[1:]:
        if split[0] != "{":
            a = split[0]
            new_substr = "\\sqrt{" + a + "}" + split[1:]
        else:
            new_substr = "\\sqrt" + split
        new_string += new_substr
    return new_string

def fix_sqrt(sample_str):
    new_str = sample_str
    right_brackets = list(find_all_occurences(new_str, '}'))
    sqrts = list(find_all_occurences(new_str, '\\sqrt'))
    for sqrt_idx in range(len(sqrts)):
        occurence = sqrts[sqrt_idx]
        
        # Assuming no nested sqrts
        # Remove occurence of "\\sqrt"
        new_str = new_str[:occurence] + new_str[occurence+5:]
        right_brackets = [x - 5 for x in right_brackets] # Update bracket indices
        # Replace the "{" corresponding to this \\sqrt occurence with "(" 
        new_str = new_str[:occurence] + "(" + new_str[occurence + 1:]
        # Replace the "}" corresponding to this \\sqrt occurence with ")^(1/2)"
        right_brackets_relative = [x - occurence for x in right_brackets]
        next_right_bracket_idx = right_brackets_relative.index(min([i for i in right_brackets_relative if i > 0]))
        next_right_bracket = right_brackets[next_right_bracket_idx]
        new_str = new_str[:next_right_bracket] + ")^(1/2)" + new_str[next_right_bracket + 1:]

        #update indicies after changing string
        sqrts = [x + 1  for x in sqrts]
        right_brackets = [x + 6 for x in right_brackets]
        
    return new_str

class NotEqual:
    def __eq__(self, other):
        return False

# Can only use non-vowels otherwise english collision risk is too high
variables_mult_regex = re.compile(r"([wqxyz])([wqxyz])")

image_regex = re.compile(r"\[asy\].*\[/asy\]", re.MULTILINE + re.DOTALL)
math_regex = re.compile(r"([\w\d\(\)]+)([*\-+/^])([\w\d\(\)\\]+)")
inflector = inflect.engine()
quick_sqrt = re.compile(r"\sqrt(\d)")
word_nums = []
for i in range(99):
    word_nums+= [(i, inflector.number_to_words(i))]

    

def strip_string(string):
    #print(f"starting_string: {string}")
    # linebreaks  
    original_string = string
    string = string.replace("\n", " ")
    #print(string)

     # remove inverse spaces
    string = string.replace("\\!", "")
    #print(string)

    # replace \\ with \
    string = string.replace("\\\\", "\\")
    #print(string)

    # replace tfrac and dfrac with frac
    string = string.replace("tfrac", "frac")
    string = string.replace("dfrac", "frac")
    #print(string)

    # remove \left and \right
    string = string.replace("\\left", "")
    string = string.replace("\\right", "")
    #print(string)

    # remove Purely display latex
    string = string.replace("\\displaystyle", "")
    string = string.replace("\\mathbf", "")
    string = string.replace("\\mathrm", "")
    string = string.replace("\\bold", "")
    string = string.replace("\\phantom", "")
    string = string.replace("\\boxed", "")
    string = string.replace("\\text", "")

    
    # convert latex brackets
    string = string.replace("\\[", " [ ")
    string = string.replace("\\]", " ] ")



    # Remove circ (degrees)
    string = string.replace("^{\\circ}", "")
    string = string.replace("^\\circ", "")

    # remove dollar signs
    string = string.replace("\\$", "")
    
    # pi
    string = string.replace("\\pi", "3.14")

    # Convert english exponent to python one
    #string = string.replace("^", " ** ")

    string = string.replace("\\le", "less than or equal to")
    string = string.replace("\\ge", "greather than or equal to")

    string = image_regex.sub("", string)

    # remove units (on the right)
    #string = remove_right_units(string)

    string = string.replace("\\cdot", "*")
    string = string.replace("\\times", "*")
    string = string.replace("\\div", "/")
   

    # remove percentage
    string = string.replace("\\%", " percent ")
    string = string.replace("\%", " percent ")
    string = string.replace("%", " percent ")

    # Space out operators
    while True:
        new_string = math_regex.sub(r" \1 \2 \3 ", string)
        if new_string == string:
            break
        string = new_string 

    # " 0." equivalent to " ." and "{0." equivalent to "{." Alternatively, add "0" if "." is the start of the string
    string = string.replace(" .", " 0.")
    string = string.replace("{.", "{0.")
    # if empty, return empty string
    if len(string) == 0:
        return string
    if string[0] == ".":
        string = "0" + string

    # to consider: get rid of e.g. "k = " or "q = " at beginning
    if len(string.split("=")) == 2:
        if len(string.split("=")[0]) <= 2:
            string = string.split("=")[1]

    # Space out implicit variable operators
    string = variables_mult_regex.sub(r"\1 * \2", string)

    # fix sqrt3 --> sqrt{3}
    string = normalize_sqrt(string)

    string = quick_sqrt.sub(r"\1 ** 0.5", string)

    # fix sqrt for real, using Alex's method
    string = fix_sqrt(string)

    # remove spaces
    #string = string.replace(" ", "")

    # \frac1b or \frac12 --> \frac{1}{b} and \frac{1}{2}, etc. Even works with \frac1{72} (but not \frac{72}1). Also does a/b --> \\frac{a}{b}
    string = normalize_fracs(string)

    # fix fracs for real, using Alex's method
    string = fix_frac(string,original_string)

    # NOTE: X/Y changed to \frac{X}{Y} in dataset, but in simple cases fix in case the model output is X/Y
    string = fix_a_slash_b(string)

    for num, num_word in word_nums:
        ostring = string
        string = re.sub(rf"\b{num_word}\b",f"{num}", string, flags=re.I)
        # if (ostring != string):
        #     print(f"{ostring} -> {string}")

    # Remove empty latex math mode
    string = string.replace("$$"," ")
    string = string.replace("$"," ")
    string = string.replace("="," equals ")
    string = string.replace("(", " ( ")
    string = string.replace(")", " ) ")
    string = string.replace("{", " { ")
    string = string.replace("}", " } ")


    string = string.strip()
    print(f"orignal_string: {original_string} striped_string: {string}")
    return string

def is_equiv(str1, str2, verbose=False):
    if str1 is None and str2 is None:
        print("WARNING: Both None")
        return True
    if str1 is None or str2 is None:
        return False

    try:
        ss1 = strip_string(str1)
        ss2 = strip_string(str2)
        if verbose:
            print(ss1, ss2)
        return ss1 == ss2
    except:
        return str1 == str2

if __name__ == "__main__":
    """
    test_in = "\\tfrac{1}{2} + \\frac1{72}"
    test_out = "\\\\frac{1}{2} + 2/3"
    print(is_equiv(test_in, test_out), "Expected", False)

    test_in = "10, 4, -2"
    test_out = "4, 10, -2"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "10, 4, 2"
    test_out = "4, 12, 2"
    print(is_equiv(test_in, test_out), "Expected", False)

    test_in = "\\tfrac{1}{2} +\\! \\frac1{72}"
    test_out = "\\\\dfrac{1}{2} +\\frac{1}{72}"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "10\\text{ units}"
    test_out = "10 "
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "10\\text{ units}"
    test_out = "100 "
    print(is_equiv(test_in, test_out), "Expected", False)

    test_in = "10"
    test_out = "\\$10"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "\\left(x-2\\right)\\left(x+2\\right)"
    test_out = "(x-2)(x+2)"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "0.1, 4, 2"
    test_out = "4, .1, 2"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "0.1"
    test_out = ".1"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "10\\%"
    test_out = "10"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "10\\sqrt{3} + \\sqrt4"
    test_out = "10\\sqrt3 + \\sqrt{4}"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "\\frac34i"
    test_out = "\\frac{3}{4}i"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "\\tfrac83"
    test_out = "\\frac{8}{3}"
    print(is_equiv(test_in, test_out), "Expected", True)

    test_in = "5x - 7y + 11z + 4 = 0"
    test_out = "x + y - z + 2 = 0"
    print(is_equiv(test_in, test_out), "Expected", False)
    
    test_in = "1/2"
    test_out = "\\frac{1}{2}"
    print(is_equiv(test_in, test_out), "Expected", True)
    """
