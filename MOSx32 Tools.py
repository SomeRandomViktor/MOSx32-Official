import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
# ============================================================
# INTERPRETADOR MOS
# ============================================================

class MOSError(Exception):
    pass


class MOSInterpreter:
    TYPES = {
        "INT": 0b00,
        "FLT": 0b01,
        "CHR": 0b10,
        "STR": 0b11,
    }

    CHAR_TO_CODE = {" ": 0x00, "\n": 0x32}
    CODE_TO_CHAR = {0x00: " ", 0x32: "\n"}

    for i, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1):
        CHAR_TO_CODE[char] = i
        CODE_TO_CHAR[i] = char

    for i, char in enumerate("0123456789", 0x34):
        CHAR_TO_CODE[char] = i
        CODE_TO_CHAR[i] = char

    EXTRA_CHARS = {
        0x1B: ".", 0x1C: ",", 0x1D: ":", 0x1E: ";",
        0x1F: "!", 0x20: "?", 0x21: "-", 0x22: "_",
        0x23: "+", 0x24: "/", 0x25: "=", 0x26: "(",
        0x27: ")", 0x28: "'", 0x29: '"', 0x2A: "@",
        0x2B: "*", 0x2C: "<", 0x2D: ">", 0x2E: "%",
        0x2F: "[", 0x30: "]", 0x31: "#", 0x33: "&",
    }

    for code, char in EXTRA_CHARS.items():
        CHAR_TO_CODE[char] = code
        CODE_TO_CHAR[code] = char

    def __init__(self, output_callback, memory_callback):
        self.output = output_callback
        self.memory_callback = memory_callback
        self.memory = {}
        self.sections = {}
        self.instructions = []
        self.pc = 0
        self.halted = False
        self.steps = 0
        self.max_steps = 100000
        self.location = "memória principal"
        self.nxt_cursors = {}

    def emit(self, text=""):
        self.output(str(text))

    @staticmethod
    def split_args(text):
        args = []
        current = []
        quoted = False
        escaped = False

        for char in text:
            if char == '"' and not escaped:
                quoted = not quoted

            if char == "," and not quoted:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(char)

            if char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False

        args.append("".join(current).strip())
        return args

    @staticmethod
    def clean_line(line):
        quoted = False
        escaped = False

        for i, char in enumerate(line):
            if char == '"' and not escaped:
                quoted = not quoted

            elif char == ";" and not quoted:
                return line[:i].strip()

            if char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False

        return line.strip()

    @staticmethod
    def address(text):
        match = re.fullmatch(
            r"\s*([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})\s*",
            text
        )

        if not match:
            raise MOSError(
                f"Endereço inválido: {text!r}. Use, por exemplo, 00 03."
            )

        return int(match.group(1), 16), int(match.group(2), 16)

    @staticmethod
    def parse_number(value):
        value = value.strip()

        if value.lower().startswith("0x"):
            return int(value[2:], 16)

        if value.lower().startswith("x"):
            return int(value[1:], 16)

        if "." in value:
            return float(value)

        return int(value)

    def cell(self, address):
        return self.memory.get(address, ("INT", 0))

    def write_cell(self, address, kind, value):
        if kind not in self.TYPES:
            raise MOSError(f"Tipo desconhecido: {kind}")

        if kind == "INT":
            value = int(value)
            if not 0 <= value <= 63:
                raise MOSError("INT deve estar entre 0 e 63.")

        elif kind == "FLT":
            value = float(value)
            if not 0 <= value <= 63:
                raise MOSError("FLT deve estar entre 0 e 63.")

        else:
            value = int(value)
            if not 0 <= value <= 63:
                raise MOSError(f"{kind} deve usar um valor de 6 bits.")

        self.memory[address] = (kind, value)
        self.memory_callback(self.memory)

    def encoded(self, address):
        kind, value = self.cell(address)
        return (self.TYPES[kind] << 6) | (int(value) & 0x3F)

    def read_typed(self, address, expected, command="PRT"):
        kind, value = self.cell(address)

        if kind != expected:
            raise MOSError(
                f"Tipo da célula ({address[0]:02X} {address[1]:02X}) "
                f"não corresponde ao tipo informado em {command}."
            )

        return value

    def prepare(self, source):
        self.instructions = []
        self.sections = {}
        self.memory = {}
        self.pc = 0
        self.halted = False
        self.steps = 0
        self.location = "memória principal"
        self.nxt_cursors = {}

        for line_number, original in enumerate(source.splitlines(), 1):
            line = self.clean_line(original)

            if not line:
                continue

            if line.upper().startswith(".LOCATE"):
                parts = line.split(maxsplit=1)

                if len(parts) != 2 or not re.fullmatch(
                    r"[xX][0-9A-Fa-f]+", parts[1]
                ):
                    raise MOSError(
                        f"Linha {line_number}: diretiva .LOCATE inválida."
                    )

                self.location = parts[1].lower()
                continue

            self.instructions.append((line_number, line))

        for index, (line_number, line) in enumerate(self.instructions):
            parts = line.split(maxsplit=1)
            command = parts[0].upper()
            argument = parts[1].strip() if len(parts) > 1 else ""

            if command == "SEC":
                if not argument:
                    raise MOSError(
                        f"Linha {line_number}: SEC exige um nome."
                    )

                if argument in self.sections:
                    raise MOSError(
                        f"Linha {line_number}: seção duplicada: {argument}."
                    )

                self.sections[argument] = index

    def jump_to(self, name):
        if name not in self.sections:
            raise MOSError(f"Seção não encontrada: {name}")

        self.pc = self.sections[name] + 1

    def execute_mov(self, args):
        if len(args) == 3:
            destination = self.address(args[0])
            kind = args[1].upper()
            raw = args[2]

            if kind not in self.TYPES:
                raise MOSError(f"Tipo inválido em MOV: {kind}")

            if kind == "CHR":
                if raw.startswith('"') and raw.endswith('"'):
                    char = raw[1:-1]

                    if len(char) != 1:
                        raise MOSError(
                            "CHR exige exatamente um caractere."
                        )

                    if char not in self.CHAR_TO_CODE:
                        raise MOSError(
                            f"Caractere fora da tabela de 6 bits: {char!r}"
                        )

                    value = self.CHAR_TO_CODE[char]
                else:
                    value = self.parse_number(raw)

            elif kind == "STR":
                if not (raw.startswith('"') and raw.endswith('"')):
                    raise MOSError('STR exige texto entre aspas.')

                text = raw[1:-1]
                sector, cell = destination
                first = sector * 256 + cell

                for offset, char in enumerate(text):
                    if char not in self.CHAR_TO_CODE:
                        raise MOSError(
                            f"Caractere fora da tabela de 6 bits: {char!r}"
                        )

                    linear = first + offset
                    target = (linear // 256, linear % 256)

                    self.write_cell(
                        target, "STR", self.CHAR_TO_CODE[char]
                    )

                return

            else:
                value = self.parse_number(raw)

            self.write_cell(destination, kind, value)
            return

        if len(args) == 4:
            start = self.address(args[0])
            end = self.address(args[1])
            kind = args[2].upper()
            raw = args[3]

            if kind != "STR":
                raise MOSError(
                    "MOV com intervalo aceita apenas o tipo STR."
                )

            if not (raw.startswith('"') and raw.endswith('"')):
                raise MOSError('STR exige texto entre aspas.')

            text = raw[1:-1]
            first = start[0] * 256 + start[1]
            last = end[0] * 256 + end[1]

            if last < first or len(text) > last - first + 1:
                raise MOSError(
                    "A string não cabe no intervalo informado."
                )

            for offset, char in enumerate(text):
                if char not in self.CHAR_TO_CODE:
                    raise MOSError(
                        f"Caractere fora da tabela de 6 bits: {char!r}"
                    )

                linear = first + offset
                self.write_cell(
                    (linear // 256, linear % 256),
                    "STR",
                    self.CHAR_TO_CODE[char]
                )

            return

        raise MOSError("MOV: use MOV endereço, tipo, valor.")

    def execute(self, source):
        self.prepare(source)

        self.emit("MOSx32 Interpreter v0.1. Desenvolvido por Vitor R. Ferreira")
        self.emit("-" * 44)
        self.emit(f"Alocado em {self.location}")
        self.emit("")

        while self.pc < len(self.instructions) and not self.halted:
            self.steps += 1

            if self.steps > self.max_steps:
                raise MOSError(
                    "Limite de instruções excedido. Possível loop infinito."
                )

            line_number, line = self.instructions[self.pc]
            self.pc += 1

            try:
                parts = line.split(maxsplit=1)
                command = parts[0].upper()
                argument = parts[1].strip() if len(parts) > 1 else ""
                args = self.split_args(argument) if argument else []

                if command in (".HALT", "HALT", "HLT"):
                    self.halted = True

                elif command in ("SEC", "ENDSEC"):
                    pass

                elif command == "MOV":
                    self.execute_mov(args)

                elif command == "CLR":
                    if len(args) != 1:
                        raise MOSError("CLR exige um endereço.")

                    self.write_cell(
                        self.address(args[0]), "INT", 0
                    )

                # NOVO COMANDO: NXT
                elif command == "NXT":
                    match = re.fullmatch(
                        r"([0-9A-Fa-f]{2})\s+MEM",
                        argument,
                        re.IGNORECASE
                    )

                    if not match:
                        raise MOSError(
                            "NXT exige setor e MEM. Exemplo: NXT 00 MEM."
                        )

                    sector = int(match.group(1), 16)

                    if sector not in self.nxt_cursors:
                        self.nxt_cursors[sector] = -1

                    self.nxt_cursors[sector] = (
                        self.nxt_cursors[sector] + 1
                    ) % 256

                elif command == "PRT":
                    if len(args) != 2:
                        raise MOSError("PRT exige endereço e tipo.")

                    kind = args[1].upper()

                    # NOVA SINTAXE: PRT 00 MEM, INT
                    if re.fullmatch(
                        r"[0-9A-Fa-f]{2}\s+MEM",
                        args[0],
                        re.IGNORECASE
                    ):
                        sector = int(args[0].split()[0], 16)

                        if sector not in self.nxt_cursors:
                            raise MOSError(
                                f"NXT ainda não foi executado para o setor "
                                f"{sector:02X}."
                            )

                        address = (
                            sector,
                            self.nxt_cursors[sector]
                        )
                    else:
                        address = self.address(args[0])

                    if kind not in self.TYPES:
                        raise MOSError(f"Tipo inválido em PRT: {kind}")

                    value = self.read_typed(address, kind)

                    if kind == "INT":
                        self.emit(str(int(value)))

                    elif kind == "FLT":
                        self.emit(str(value))

                    elif kind == "CHR":
                        self.emit(
                            self.CODE_TO_CHAR.get(
                                int(value), f"[CHR {int(value):02X}]"
                            )
                        )

                    else:
                        self.emit(
                            self.CODE_TO_CHAR.get(
                                int(value), f"[STR {int(value):02X}]"
                            )
                        )

                elif command in ("JMP", "JIB", "JIS", "JIE"):
                    if command == "JMP":
                        if len(args) != 1:
                            raise MOSError(
                                "JMP exige o nome de uma seção."
                            )

                        self.jump_to(args[0])

                    else:
                        if len(args) != 3:
                            raise MOSError(
                                f"{command} exige seção e dois endereços."
                            )

                        section = args[0]
                        a1 = self.address(args[1])
                        a2 = self.address(args[2])

                        kind1, value1 = self.cell(a1)
                        kind2, value2 = self.cell(a2)

                        if kind1 != kind2:
                            raise MOSError(
                                "Comparação entre células de tipos diferentes."
                            )

                        condition = (
                            (command == "JIB" and value1 > value2)
                            or (command == "JIS" and value1 < value2)
                            or (command == "JIE" and value1 == value2)
                        )

                        if condition:
                            self.jump_to(section)

                elif command in ("ADD", "SUB", "MUL", "DIV"):
                    if len(args) != 3:
                        raise MOSError(
                            f"{command} exige destino, origem e valor/endereço."
                        )

                    destination = self.address(args[0])
                    source_address = self.address(args[1])
                    kind, left = self.cell(source_address)

                    if kind not in ("INT", "FLT"):
                        raise MOSError(
                            f"{command} só opera com INT ou FLT."
                        )

                    try:
                        right_address = self.address(args[2])
                        right_kind, right = self.cell(right_address)

                        if right_kind != kind:
                            raise MOSError(
                                "Tipos diferentes na operação."
                            )

                    except MOSError as error:
                        if not str(error).startswith("Endereço inválido"):
                            raise

                        right = self.parse_number(args[2])

                    if command == "ADD":
                        result = left + right
                    elif command == "SUB":
                        result = left - right
                    elif command == "MUL":
                        result = left * right
                    else:
                        if right == 0:
                            raise MOSError("Divisão por zero.")

                        result = left / right

                    if kind == "INT":
                        if result != int(result):
                            raise MOSError(
                                "Resultado fracionário não cabe em INT."
                            )

                        result = int(result)

                    self.write_cell(destination, kind, result)

                elif command == "CPY":
                    if len(args) != 3:
                        raise MOSError(
                            "CPY exige origem, destino e tipo."
                        )

                    source_address = self.address(args[0])
                    destination = self.address(args[1])
                    kind = args[2].upper()

                    value = self.read_typed(
                        source_address, kind, "CPY"
                    )

                    self.write_cell(destination, kind, value)

                else:
                    raise MOSError(
                        f"Comando desconhecido: {command}"
                    )

            except (ValueError, IndexError, OverflowError) as error:
                raise MOSError(
                    f"Linha {line_number}: valor inválido: {error}"
                ) from error

            except MOSError as error:
                raise MOSError(
                    f"Linha {line_number}: {error}"
                ) from error

        if self.halted:
            self.emit("\n[Programa encerrado por HALT.]")
        else:
            self.emit("\n[Fim do arquivo.]")

        self.emit(f"Instruções executadas: {self.steps}")


# ============================================================
# EDITOR MOS
# ============================================================

class MOSEditor:
    def __init__(self, root):
        self.root = root
        self.current_file = None
        self.theme = "dark"
        self.output_window = None
        self.output_text = None
        self.memory_text = None
        self.interpreter = None
        self._color_job = None

        self.themes = {
            "dark": {
                "window": "#202124",
                "editor": "#171717",
                "text": "#eeeeee",
                "menu": "#303134",
                "select": "#365b83",
                "status": "#303134",
                "output": "#111111",
                "gutter": "#252525",
                "keyword": "#569CD6",
                "number": "#B5CEA8",
                "string": "#CE9178",
                "comment": "#6A9955",
                "type": "#C586C0",
                "address": "#DCDCAA",
                "directive": "#4EC9B0",
                "operator": "#D7BA7D",
                "section": "#D7BA7D",
            },
            "light": {
                "window": "#f2f2f2",
                "editor": "#ffffff",
                "text": "#202020",
                "menu": "#e2e2e2",
                "select": "#b8d7ff",
                "status": "#e2e2e2",
                "output": "#ffffff",
                "gutter": "#eeeeee",
                "keyword": "#0000CC",
                "number": "#098658",
                "string": "#A31515",
                "comment": "#008000",
                "type": "#AF00DB",
                "address": "#795E26",
                "directive": "#267F99",
                "operator": "#795E26",
                "section": "#795E26",
            },
        }

        self.root.geometry("1000x650")
        self.root.minsize(650, 420)

        self._make_menu()

        self.editor_frame = tk.Frame(root)
        self.editor_frame.pack(fill="both", expand=True)

        self.gutter = tk.Text(
            self.editor_frame,
            width=5,
            padx=8,
            pady=12,
            state="disabled",
            takefocus=0,
            wrap="none",
            font=("Consolas", 12),
            borderwidth=0,
            highlightthickness=0,
        )
        self.gutter.pack(side="left", fill="y")

        self.editor = tk.Text(
            self.editor_frame,
            wrap="none",
            undo=True,
            font=("Consolas", 12),
            padx=12,
            pady=12,
            borderwidth=0,
            highlightthickness=0,
        )
        self.editor.pack(side="left", fill="both", expand=True)

        self.scroll_y = tk.Scrollbar(
            self.editor_frame,
            orient="vertical",
            command=self._scroll_editor,
        )
        self.scroll_y.pack(side="right", fill="y")
        self.editor.configure(yscrollcommand=self._sync_scroll)

        self.scroll_x = tk.Scrollbar(
            root,
            orient="horizontal",
            command=self.editor.xview,
        )
        self.scroll_x.pack(fill="x")
        self.editor.configure(xscrollcommand=self.scroll_x.set)

        self.editor.edit_modified(False)
        self.editor.bind("<KeyRelease>", self._editor_changed)
        self.editor.bind("<<Paste>>", self._schedule_color)
        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<MouseWheel>", self._sync_gutter_event)
        self.editor.bind("<Configure>", self._sync_gutter_event)

        self.status_var = tk.StringVar(value="Pronto")
        self.status = tk.Label(
            root,
            textvariable=self.status_var,
            anchor="w",
            padx=8,
            pady=4,
        )
        self.status.pack(fill="x", side="bottom")

        self.root.bind("<Control-n>", lambda event: self.new_file())
        self.root.bind("<Control-o>", lambda event: self.open_file())
        self.root.bind("<Control-s>", lambda event: self.save_file())
        self.root.bind(
            "<Control-Shift-S>", lambda event: self.save_as()
        )
        self.root.bind("<F5>", lambda event: self.run_code())
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.apply_theme()
        self.update_line_numbers()
        self.update_title()

    # --------------------------------------------------------
    # MENUS
    # --------------------------------------------------------

    def _make_menu(self):
        self.menu = tk.Menu(self.root)

        file_menu = tk.Menu(self.menu, tearoff=False)
        file_menu.add_command(
            label="Novo", command=self.new_file, accelerator="Ctrl+N"
        )
        file_menu.add_command(
            label="Abrir...", command=self.open_file, accelerator="Ctrl+O"
        )
        file_menu.add_command(
            label="Salvar", command=self.save_file, accelerator="Ctrl+S"
        )
        file_menu.add_command(
            label="Salvar como...",
            command=self.save_as,
            accelerator="Ctrl+Shift+S",
        )
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.close_app)
        self.menu.add_cascade(label="Arquivo", menu=file_menu)

        run_menu = tk.Menu(self.menu, tearoff=False)
        run_menu.add_command(
            label="Executar", command=self.run_code, accelerator="F5"
        )
        self.menu.add_cascade(label="Executar", menu=run_menu)

        settings_menu = tk.Menu(self.menu, tearoff=False)
        settings_menu.add_command(
            label="Tema escuro",
            command=lambda: self.set_theme("dark"),
        )
        settings_menu.add_command(
            label="Tema claro",
            command=lambda: self.set_theme("light"),
        )
        self.menu.add_cascade(
            label="Configurações", menu=settings_menu
        )

        self.root.config(menu=self.menu)
        self.menus = [self.menu, file_menu, run_menu, settings_menu]

    # --------------------------------------------------------
    # NUMERAÇÃO DE LINHAS E ROLAGEM
    # --------------------------------------------------------

    def _scroll_editor(self, *args):
        self.editor.yview(*args)
        self.gutter.yview(*args)

    def _sync_scroll(self, first, last):
        self.scroll_y.set(first, last)
        self.gutter.yview_moveto(first)

    def _sync_gutter_event(self, event=None):
        self.root.after_idle(self.update_line_numbers)

    def _editor_changed(self, event=None):
        self.update_line_numbers()
        self._schedule_color()

    def update_line_numbers(self):
        line_count = int(
            self.editor.index("end-1c").split(".")[0]
        )

        numbers = "\n".join(
            str(i) for i in range(1, line_count + 1)
        )

        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", numbers)
        self.gutter.configure(state="disabled")
        self.gutter.yview_moveto(self.editor.yview()[0])

    # --------------------------------------------------------
    # TEMAS
    # --------------------------------------------------------

    def apply_theme(self):
        colors = self.themes[self.theme]

        self.root.configure(bg=colors["window"])
        self.editor_frame.configure(bg=colors["window"])

        self.editor.configure(
            bg=colors["editor"],
            fg=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["select"],
            selectforeground=colors["text"],
        )

        # tk.Text não possui disabledforeground.
        self.gutter.configure(
            bg=colors["gutter"],
            fg="#858585",
        )

        self.status.configure(
            bg=colors["status"],
            fg=colors["text"],
        )

        for menu in self.menus:
            menu.configure(
                background=colors["menu"],
                foreground=colors["text"],
                activebackground=colors["select"],
                activeforeground=colors["text"],
            )

        if (
            self.output_window is not None
            and self.output_window.winfo_exists()
        ):
            self.output_window.configure(bg=colors["window"])

            self.output_text.configure(
                bg=colors["output"],
                fg=colors["text"],
                insertbackground=colors["text"],
                selectbackground=colors["select"],
            )

            self.memory_text.configure(
                bg=colors["output"],
                fg=colors["text"],
                insertbackground=colors["text"],
                selectbackground=colors["select"],
            )

        self.colorir_codigo()

    def set_theme(self, theme):
        self.theme = theme
        self.apply_theme()

        if theme == "dark":
            self.status_var.set("Tema escuro ativado")
        else:
            self.status_var.set("Tema claro ativado")

    # --------------------------------------------------------
    # COLORAÇÃO DO CÓDIGO
    # --------------------------------------------------------

    def _on_modified(self, event=None):
        if self.editor.edit_modified():
            self.update_title()
            self.editor.edit_modified(False)

    def _schedule_color(self, event=None):
        if self._color_job is not None:
            try:
                self.root.after_cancel(self._color_job)
            except tk.TclError:
                pass

        self._color_job = self.root.after(
            80, self.colorir_codigo
        )

    def colorir_codigo(self, event=None):
        self._color_job = None

        codigo = self.editor.get("1.0", "end-1c")
        colors = self.themes[self.theme]

        tags = (
            "keyword",
            "number",
            "string",
            "comment",
            "type",
            "address",
            "directive",
            "operator",
            "section",
        )

        for tag in tags:
            self.editor.tag_remove(tag, "1.0", "end")
            self.editor.tag_configure(
                tag, foreground=colors[tag]
            )

        def apply_tag(pattern, tag, flags=re.IGNORECASE):
            for match in re.finditer(pattern, codigo, flags):
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                self.editor.tag_add(tag, start, end)

        # Strings e comentários
        apply_tag(r'"(?:\\.|[^"\\])*"', "string", 0)
        apply_tag(r";[^\n]*", "comment", 0)

        # Diretivas
        apply_tag(
            r"^\s*\.LOCATE\b[^\n]*|^\s*\.HALT\b",
            "directive",
            re.IGNORECASE | re.MULTILINE,
        )

        # Comandos
        apply_tag(
            r"\b(MOV|ADD|SUB|MUL|DIV|PRT|CLR|SEC|ENDSEC|"
            r"JMP|JIB|JIS|JIE|CPY|NXT|HALT|HLT)\b",
            "keyword",
        )

        # Tipos
        apply_tag(r"\b(INT|FLT|CHR|STR|MEM)\b", "type")

        # Declarações de seção
        apply_tag(
            r"^\s*SEC\s+\w+",
            "section",
            re.IGNORECASE | re.MULTILINE,
        )

        # Endereços de memória
        apply_tag(
            r"\b[0-9A-Fa-f]{2}\s+[0-9A-Fa-f]{2}\b",
            "address",
        )

        # Endereços de localização
        apply_tag(r"\bx[0-9A-Fa-f]+\b", "address")

        # Números decimais e hexadecimais
        apply_tag(
            r"\b(?:0x[0-9A-Fa-f]+|x[0-9A-Fa-f]+|\d+(?:\.\d+)?)\b",
            "number",
        )

        self.editor.tag_raise("string")
        self.editor.tag_raise("comment")

    # --------------------------------------------------------
    # ARQUIVOS
    # --------------------------------------------------------

    def update_title(self):
        name = (
            self.current_file.name
            if self.current_file
            else "Sem título"
        )

        dirty = "*" if self.editor.edit_modified() else ""

        self.root.title(
            f"{dirty}{name} - mOS Code Editor"
        )

    def confirm_unsaved(self):
        if not self.editor.edit_modified():
            return True

        answer = messagebox.askyesnocancel(
            "Alterações não salvas",
            "Deseja salvar as alterações antes de continuar?",
            parent=self.root,
        )

        if answer is None:
            return False

        if answer:
            return self.save_file()

        return True

    def new_file(self):
        if not self.confirm_unsaved():
            return

        self.editor.delete("1.0", "end")
        self.current_file = None
        self.editor.edit_modified(False)

        self.update_title()
        self.update_line_numbers()
        self.status_var.set("Novo arquivo")
        self.colorir_codigo()

    def open_file(self):
        if not self.confirm_unsaved():
            return

        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Abrir arquivo",
            filetypes=[
                ("Arquivos mOS", "*.mos"),
                ("Todos os arquivos", "*.*"),
            ],
        )

        if not filename:
            return

        try:
            content = Path(filename).read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as error:
            messagebox.showerror(
                "Erro ao abrir arquivo",
                str(error),
                parent=self.root,
            )
            return

        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self.current_file = Path(filename)
        self.editor.edit_modified(False)

        self.update_title()
        self.update_line_numbers()
        self.status_var.set(
            f"Arquivo aberto: {self.current_file.name}"
        )
        self.colorir_codigo()

    def save_file(self):
        if self.current_file is None:
            return self.save_as()

        return self._write_file(self.current_file)

    def save_as(self):
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar arquivo como",
            defaultextension=".mos",
            initialfile="programa.mos",
            filetypes=[
                ("Arquivos mOS", "*.mos"),
                ("Todos os arquivos", "*.*"),
            ],
        )

        if not filename:
            return False

        path = Path(filename)

        if path.suffix.lower() != ".mos":
            path = path.with_suffix(".mos")

        return self._write_file(path)

    def _write_file(self, path):
        try:
            path.write_text(
                self.editor.get("1.0", "end-1c"),
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror(
                "Erro ao salvar arquivo",
                str(error),
                parent=self.root,
            )
            return False

        self.current_file = path
        self.editor.edit_modified(False)
        self.update_title()

        self.status_var.set(f"Salvo: {path.name}")
        return True

    # --------------------------------------------------------
    # JANELA DE EXECUÇÃO E MEMÓRIA
    # --------------------------------------------------------

    def _ensure_output_window(self):
        if (
            self.output_window is not None
            and self.output_window.winfo_exists()
        ):
            self.output_window.deiconify()
            self.output_window.lift()
            return

        self.output_window = tk.Toplevel(self.root)
        self.output_window.title(
            "Execução - mOS Code Editor"
        )
        self.output_window.geometry("950x450")
        self.output_window.minsize(650, 300)

        container = tk.PanedWindow(
            self.output_window,
            orient="horizontal",
            sashwidth=6,
        )
        container.pack(fill="both", expand=True)

        output_frame = tk.Frame(container)
        memory_frame = tk.Frame(container)

        container.add(output_frame, minsize=220)
        container.add(memory_frame, minsize=350)

        tk.Label(
            output_frame,
            text="SAÍDA",
            anchor="w",
            padx=8,
        ).pack(fill="x")

        self.output_text = tk.Text(
            output_frame,
            wrap="word",
            font=("Consolas", 11),
            padx=10,
            pady=10,
            borderwidth=0,
            state="disabled",
        )
        self.output_text.pack(fill="both", expand=True)

        tk.Label(
            memory_frame,
            text="MEMÓRIA (hexadecimal)",
            anchor="w",
            padx=8,
        ).pack(fill="x")

        self.memory_text = tk.Text(
            memory_frame,
            wrap="none",
            font=("Consolas", 10),
            padx=8,
            pady=8,
            borderwidth=0,
            state="disabled",
        )
        self.memory_text.pack(fill="both", expand=True)

        self.output_window.protocol(
            "WM_DELETE_WINDOW",
            self.output_window.withdraw,
        )

        self.apply_theme()
        self.refresh_memory({})

    def refresh_memory(self, memory):
        if self.memory_text is None:
            return

        if (
            self.output_window is None
            or not self.output_window.winfo_exists()
        ):
            return

        headers = "     " + " ".join(
            f"{i:02X}" for i in range(16)
        )

        lines = [headers]

        for sector in range(16):
            row = [f"{sector:02X}  "]

            for cell in range(16):
                kind, value = memory.get(
                    (sector, cell),
                    ("INT", 0),
                )

                raw = (
                    MOSInterpreter.TYPES[kind] << 6
                ) | (int(value) & 0x3F)

                row.append(f"{raw:02X}")

            lines.append(" ".join(row))

        self.memory_text.configure(state="normal")
        self.memory_text.delete("1.0", "end")
        self.memory_text.insert("1.0", "\n".join(lines))
        self.memory_text.configure(state="disabled")

    def append_output(self, text=""):
        if self.output_text is None:
            return

        self.output_text.configure(state="normal")
        self.output_text.insert("end", str(text) + "\n")
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

        self.root.update_idletasks()

    def run_code(self):
        code = self.editor.get("1.0", "end-1c")

        self._ensure_output_window()

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

        self.refresh_memory({})

        self.interpreter = MOSInterpreter(
            self.append_output,
            self.refresh_memory,
        )

        try:
            self.interpreter.execute(code)
            self.status_var.set("Execução concluída")

        except MOSError as error:
            self.append_output("")
            self.append_output(f"ERRO: {error}")
            self.status_var.set("Erro durante a execução")

        except Exception as error:
            self.append_output(
                f"ERRO INTERNO: {type(error).__name__}: {error}"
            )
            self.status_var.set(
                "Erro interno do interpretador"
            )

        self.output_window.lift()

    # --------------------------------------------------------
    # ENCERRAMENTO
    # --------------------------------------------------------

    def close_app(self):
        if self.confirm_unsaved():
            self.root.destroy()



# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()

    # Ícone do MOS: funciona no Python e no executável PyInstaller.
    if getattr(sys, "frozen", False):
        pasta_programa = Path(sys.executable).parent
    else:
        pasta_programa = Path(__file__).resolve().parent

    caminho_icone = pasta_programa / "mos.ico"

    if caminho_icone.exists():
        try:
            root.iconbitmap(str(caminho_icone))
        except tk.TclError:
            pass

    app = MOSEditor(root)
    root.mainloop()

