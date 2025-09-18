# VulWitch: Machine Learning Based Static Code Analyzer

Static code analysis is a powerful technique to help programmers discover bugs
and vulnerabilities in their code.static analysis occurs without executing the 
code in order to unearth information of interest by only inspecting code, which is
usually represented in a structured form, e.g., abstract syntax tree (AST).
Traditionally, a static analyzer either searches code patterns by matching
handwritten rules against ASTs, such as [Semgrep][semgrep], or exercises more
compilcated such as control flow/data analysis like Meta's [Infer][meta infer].
Given the nature of pattern matching, we believe that artificial intelligence
(AI) fits well into the realm of static code analysis, hench VulWitch, a
machine-learning-based code analyzer. We believe that machine learning methods
could ease implementation and iterative improvement of an analyzer by
automatically learning from a huge amount of existing and future bugs and
vulnerabilities. Moreover, we do not anticipate that AI-powered code analyzers
will entirely replace traditional ones. We believe they could work together to 
give more accurate results by cross validation results from each other.

## Design of VulWitch

### Use case diagram

![Use case diagram](/doc/img/VulWitch_Use_Cases.jpeg)
You can view the above use case diagram at [Lucidcart](https://lucid.app/lucidchart/d8eb6231-b3fd-45bd-9ab9-d64b39817447/edit?viewport_loc=88%2C-239%2C1939%2C931%2C0_0&invitationId=inv_1ae287ae-0cdc-4c3c-ba2a-3939ef401224).

| Use Case Name | View abstract syntax trees of a source code file |
| ------------- | ------------------------------------------------ |
| Actors        | User |
| Preconditions | User gives a source file containing syntactically correct code. |
| Goal          | Let a user view abstract syntax trees of a source file. |
| Scenario      | 1. User give a source code file. <br> 2. The file is parsed, and abtract syntax trees of are created. <br> 3. ASTs are serialized and printed. |
| Exceptions    | The source file has code with invalid syntaxes. |

| Use Case Name | Parse code and create abstract syntax trees |
| ------------- | ------------------------------------------- |
| Actors        | User |
| Preconditions | User inputs a source file which does not have syntactical errors. |
| Goal          | Parse the file according to syntaxes of the language specification, and create abstract syntax trees. |
| Scenario      | 1. User inputs a code file. <br> 2. VulWitch parses the file and generate abstract syntax trees for it. |
| Exceptions    | VulWitch should raise errors if the file has syntax errors. |

| Use Case Name | Serialize abstract syntax trees |
| ------------- | ------------------------------- |
| Actors        | User |
| Preconditions | A valid source file is parsed, and abtract syntax trees are created. |
| Goal          | Use strings to represent abtract syntax trees. |
| Scenario      | 1. User gives a code file. <br> 2. VulWitch parses the file and create abstract syntax trees. <br> 3. VulWitch serializes ASTs into strings to present them to User. |
| Exceptions    | Abstract syntax trees are invalid. |

| Use Case Name | Analyze a source code file for common vulnerabilities |
| ------------- | ----------------------------------------------------- |
| Actors        | User |
| Preconditions | User inputs an exitings source file which contains well-formed code. |
| Goal          | Detect all bugs and vulnerabilities in a source file. |
| Scenario      | 1. User gives a source file. <br> 2. VulWitch parse the file and create ASTs. <br> 3. AI Model analyzes function ASTs and reports all detected vulnerabilities. <br> 4. VulWitch generates a detailed report of these vulnerabilities. |
| Exceptions    | 1. The source file can not be found at the specific path. <br> 2. The file contains invalid code. |

| Use Case Name | Detect common vulnerabilites in the AST of a function |
| ------------- | ----------------------------------------------------- |
| Actors        | AI Model |
| Preconditions | VulWitch gives the AST of a syntactically valid function. |
| Goal          | Detect vulnerabilities in a function AST. |
| Scenario      | 1. VulWitch feeds a function AST into AI Model. <br> AI Model analyzes the AST and reports any detected vulnerabilities along with their categories.  |
| Exceptions    | The abstract syntax tree is ill-formed. |

### Class diagram

![Class diagram](/doc/img/VulWitch_Class_Diagram.jpeg)

You can view the above class diagram at [Lucidcart](https://lucid.app/lucidchart/ec2b87ac-5dfa-4889-ab5c-39b24d891e78/edit?viewport_loc=-1218%2C392%2C2336%2C1122%2C0_0&invitationId=inv_86096d55-2e28-49cd-bc07-d5aadef3dc46).

## Security plan

### Security goal

1. Vulnerability detection performance

- Detect common vulnerabilities such as injection attacks, buffer overflows, and
insecure cryptographic practices such as hardcoded secrets and API keys.

- Map detected vulnerabilities to different categories according to security
standards, e.g., OWASP Top 10, CERT secure coding guidelines, and CWE.

- Maintain a balance between intrinsically conflicting false positive and false
negative rates to ensure high availability for developers.

2. Runtime performance

- Be able to analyze a single source file in constant time.

- Be able to efficiently analyze projects of large codebases so that it does not
slow the development process.

- Offer support to examine independent source files in parallel to speed up
analysis.

### Security metrics

1. Vulnerability detection performance

- Rate of false positives and false negatives to show inaccuracy of Vulwitch
based on training data test sets.

- Display score for true positive and true negitive to see how many issues found
by the model proved to be issued based on standards.

- Display Precision, recall, and F-1 score of our AI model, in order to evaluate
the accuracy of vulnerability detection of the model.

- Accuracy of mapping vulnerabilities according to secure standards.

2. Runtime performance

- Time to detect vulnerabilities for a single source file.

- Time to run analysis against a project having a large code size.

- Speedup of analyzing independent source files in parallel.

[semgrep]: https://github.com/semgrep/semgrep
[meta infer]: https://github.com/facebook/infer
