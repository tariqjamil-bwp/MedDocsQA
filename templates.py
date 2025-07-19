# templates.py

"""
This file contains simplified Jinja2 templates without conditional 'if' blocks.

This version is appropriate if you want every section heading to always be
visible in the final document. The `| default('[N/A]')` filter is used to
provide placeholder text for any missing data.
"""

# #############################################################################
# --- FULL TEMPLATE ---
# #############################################################################
OUTPUT_TEMPLATE_FULL_JINJA = """
## Question #: {{ question_num | default('[N/A]') }}

**CLINICAL SCENARIO:**
{{ question_desc | default('[N/A]') | safe }}

**QUESTION LINE:**
{{ question_line | default('[N/A]') | safe }}

**OPTIONS:**\n
{{ options | safe | replace('\\n', '\\n\\n') }}

**CORRECT CHOICE:**
{{ correct_choice | default('[N/A]') }}

**REASONING:**
{{ reasoning | default('[N/A]') | safe }}

---

**> DESCRIPTION:**
{{ updated_description | default('[N/A]') | safe }}

**> OPTIONS:**\n
{{ updated_options | safe | replace('\\n', '\\n\\n') }}

**> CORRECT CHOICE:**
{{ updated_correct_choice | default('[N/A]') }}   ({{ updated_correct_choice_text | default('[N/A]') }})

**> REASONING:**
{{ updated_reasoning | default('[N/A]') | safe }}


"""

# #############################################################################
# --- ORIGINAL TEMPLATE ---
# #############################################################################
OUTPUT_TEMPLATE_ORIGINAL_JINJA = """
## Question #: {{ question_num | default('[N/A]') }}

**CLINICAL SCENARIO:**
{{ question_desc | default('[N/A]') | safe }}

**QUESTION LINE:**
{{ question_line | default('[N/A]') | safe }}

**> OPTIONS:**\n
{{ updated_options | safe | replace('\\n', '\\n\\n') }}

**> CORRECT CHOICE:**
{{ updated_correct_choice | default('[N/A]') }}   ({{ updated_correct_choice_text | default('[N/A]') }})

**REASONING:**
{{ reasoning | default('[N/A]') | safe }}


"""

# #############################################################################
# --- UPDATED TEMPLATE ---
# #############################################################################
OUTPUT_TEMPLATE_UPDATED_JINJA = """
## Question #: {{ question_num | default('[N/A]') }}

**> CLINICAL SCENARIO:**
{{ updated_description | default('[N/A]') | safe }}

**QUESTION LINE:**
{{ question_line | default('[N/A]') | safe }}

**> OPTIONS:**\n
{{ updated_options | safe | replace('\\n', '\\n\\n') }}

**> CORRECT CHOICE:**
{{ updated_correct_choice | default('[N/A]') }}   ({{ updated_correct_choice_text | default('[N/A]') }})

**> REASONING:**
{{ updated_reasoning | default('[N/A]') | safe }}


"""