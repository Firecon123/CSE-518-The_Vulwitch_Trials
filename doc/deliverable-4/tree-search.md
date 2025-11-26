# Vulnerability Detection Based on Abstract Syntax Tree Searching

## 1 Introduction

Our have submited a static code analyzer powered by an artifical
intelligence (AI) model. However, this approach suffers two major problems.
First, it would run unsatisfactorily slow as the model has a significant amount
of weights and the GPU (or multiple ones) to run the model may not have enough
computing power. Moreover, traning a model with good accuracy is nontrivial and
requires enormous research and engineering efforts. So as to alleviate these two
issues in some user cases, our team provide a practically usable and flexible
solution based tree searching, i.e., searching certain patterns against the
abstract syntax tree of a source file.

## 2 Architecture

### 2.1 Parsing Enhanced by Compilation Database

For real-world projects, a single C source file usually relies on header files
for external declarations and macro definitions. C code using macros may appear
to have syntax errors at first glance even though it is valid after
preprocessing, e.g.,

```c
INT
INTERNAL (strtol) (const STRING_TYPE *nptr, STRING_TYPE **endptr,
		   int base, int group)
{
  return INTERNAL (__strtol_l) (nptr, endptr, base, group, false,
				_NL_CURRENT_LOCALE);
}
libc_hidden_def (INTERNAL (strtol))
```

One way to mitigate this problem is obviously to first process a code file using
a C preprocessor. However, this approach often depends on the provision of paths
where a preprocessor can search for header files. While a preprocessors knows
how a C standard library file can be resolved, it does not have clues on where
it can find third-party header files. Of course, we can ask users to offer these
paths, but it can be tedious for big real-world C projects. To resolve the
issue, our tool supports extract header directories from
[compilation database](https://clang.llvm.org/docs/JSONCompilationDatabase.html).
Currently, header search paths and macro definitions are extracted and utilized
for parsing abstract syntax trees (AST).

### 2.2 Rules and Plugins

Given an abstract syntax tree (AST), one can discover a considerable amount of
vulnerabilities by matching tree nodes locally, such as use of the unsafe C
functions `gets`. Although this approach has a limited capability of
vulnerability detection, it has advantages of detection speed. In addition,
users can easily extend it by providing custom matching rules.

We provide a scalable way to construct matching rules via a simple plugin
framework. The matching rules are essentially [S-expressions](https://en.wikipedia.org/wiki/S-expression)
and can been considered as a domain specific language (DSL). At present, we
provide three categories of rules. The first one is used to match a syntax
construct of C, such as a function call or a function definition. The second one
is a wildcard matching everything, and the last one acts like logical operators
such as `&&` and `!`. For example,

```yaml
rules:
  - id: unsafe function gets
    pattern: >
      (FuncCall
        name: (ID name: (#eq "gets")))
    message: >-
      Function `gets` is unsafe.
      Please consider using `fgets` instead.
      Refer to CWE-242: Use of Inherently Dangerous Function.
    severity: HIGH
    confidence: HIGH
  - id: assignments in logical operations
    pattern: >
      (#any
        (BinaryOp
          op: (#any (#eq "&&") (#eq "||"))
          lhs: (Assignment))
        (BinaryOp
          op: (#any (#eq "&&") (#eq "||"))
          rhs: (Assignment)))
    message: >-
      Assignment used in conditional expression (
      possible error: use '==' for comparison?)
    severity: LOW
    confidence: LOW
```

the first rule above matches calls to the function `gets` which is unsafe and
can result in buffer overflows. The second rule looks for the use of
assignments as operands of logical operators, which might result from misusing
`=` for equality comparison.

Moreover, our tool allow users to extend the DSL for rules by writing their own
pattern constructors. Users can extend the following `AbstractPattern` and
utlize `AbstractPatternContext` to construct children representing other known
patterns. Later, custom plugins can be loaded by specifying the path to the
Python file containing these plugins.

```python
class AbstractPatternContext(metaclass=ABCMeta):
    @abstractmethod
    def build(self, data: Any) -> "AbstractPattern[Any]":
        pass


class AbstractPattern[SubjectT](metaclass=ABCMeta):
    @abstractmethod
    def match(self, subject: SubjectT) -> bool:
        pass

    @classmethod
    @abstractmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        pass
```

For instance, the `#any` pattern matches if any of the included patterns does.
It is implemented as follows:

```python
class AnyPattern(AbstractPattern[Any]):
    _patterns: Tuple[AbstractPattern[Any], ...]

    def __init__(self, patterns: Sequence[AbstractPattern[Any]]) -> None:
        self._patterns = tuple(patterns)

    @override
    def match(self, subject: Any) -> bool:
        return any(map(lambda p: p.match(subject), self._patterns))

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if not isinstance(data, list) or len(data) == 0:
            return None
        if data[0] != Symbol("#any"):
            return None
        patterns = []
        for subdata in data[1:]:
            patterns.append(context.build(subdata))
        return cls(patterns)
```

## 3 Case Study

### 3.1 Redis

We test the effectiveness of the proposed tool by using it to detect
vulnerabilities in Redis' source code. You can repeat the test by the following
instructions, assuming you have Docker installed.

```bash
$ docker run -it --name redis-builder ubuntu:24.04
# The following commands are executed in the Docker container `redis-builder`
$ apt-get update
$ apt-get install -y --no-install-recommends \
    ca-certificates wget dpkg-dev gcc g++ libc6-dev libssl-dev make git cmake \
    python3 python3-pip python3-venv python3-dev unzip rsync clang automake \
    autoconf libtool bear curl
$ cd $HOME
$ mkdir redis && cd redis
$ curl -o redis-8.4.0.tar.gz -L https://github.com/redis/redis/archive/refs/tags/8.4.0.tar.gz
$ tar -xf redis-8.4.0.tar.gz
$ cd /root/redis-8.4.0
$ export BUILD_TLS=yes BUILD_WITH_MODULES=yes INSTALL_RUST_TOOLCHAIN=yes DISABLE_WERRORS=yes
$ bear -- make -j "$(nproc)" all
```

If building redis succeeds, there will be a file named
`/root/redis/redis-8.4.0/compile_commands.json`, which is a compilation database
in JSON format and records commmands to build every C source files.

```bash
# The following commands are executed in the Docker container `redis-builder`
$ python3 -m venv --promt vulwitch $HOME/vulwitch-env
$ source $HOME/vulwitch-env/bin/activate
(vulwitch) $ git clone git@github.com:Firecon123/CSE-518-The_Vulwitch_Trials.git /root/vulwitch
(vulwitch) $ cd /root/vulwitch
(vulwitch) $ pip3 install build wheel
(vulwitch) $ python3 -m build --wheel
(vulwitch) $ pip3 install ./dist/vulwitch-0.1.0-py3-none-any.whl
(vulwitch) $ vulwitch analyze \
    --jobs $(nproc) \
    --rule /root/vulwitch/rules.yaml \
    --depress-warnings \
    --compdb /root/redis/redis-8.4.0/compile_commands.json
```

Based on current matching rules, the output should look like:

```bash
analyzed 482/776 source files
...
- source_file: /home/hongbin/Downloads/redis/redis-8.4.0/modules/redisearch/src/src/obfuscation/obfuscation_api.c
  vulnerbilities:
  - location:
      column: 3
      line: 19
    message: 'Function `strcpy` is unsafe. Please consider using `strlcpy` instead.
      Refer to CWE-676: Use of Potentially Dangerous Function.'
    severity: HIGH
- source_file: /home/hongbin/Downloads/redis/redis-8.4.0/modules/redisearch/src/src/trie/trie.c
  vulnerbilities:
  - location:
      column: 16
      line: 713
    message: Consider not using the function `rand` as it makes no guarantees as to
      the quality of the random sequence produced. Refer to CERT C Secure Coding MSC30-C.
    severity: LOW
- source_file: /home/hongbin/Downloads/redis/redis-8.4.0/modules/redisearch/src/src/trie/trie_type.c
  vulnerbilities:
  - location:
      column: 40
      line: 272
    message: Consider not using the function `rand` as it makes no guarantees as to
      the quality of the random sequence produced. Refer to CERT C Secure Coding MSC30-C.
    severity: LOW
...
analysis took 42.230 seconds
```

## 4 Limitations

Currently, we rely on the third-party `pycparser` to parse AST which only
supports C99 and a very few of commonly used language extensions of GCC and
clang. Therefore, our current AST parsing functionality likely fails for many
real-world projects. Our current workaround is to define some of these language
extensions as macros. Since our support for these extensions is not exhaustive,
failures of parsing may still occur. One of the directions for future work is to
expand `pycparser`'s support of widely used language extensions.

Our tree-search-based approach is clumsy to handle use-after-free and
double-free issues as detecting them needs data and control flow analysis using
techniques of abstract interpretation and symbolic execution. Thus, lowering
down AST to control flow graphs (CFGs) could be future work.
