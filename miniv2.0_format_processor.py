import subprocess

data_path = subprocess.check_output(
    ["git", "config", "--get", "data.path"], text=True
).strip()

original_v2 = open(f"{data_path}/hprc-v2.0-mc-grch38.sv.gfa", "r")
updated_v2 = open(f"{data_path}/hprc-v2.0-minigraph-grch38.gfa", "w")

for line in original_v2:
    if "SN:Z:GRCh38#0#" in line:
        tag_index = line.index("SN:Z:GRCh38#0#")
        chromosome = line[tag_index+14:tag_index+20].split("\t")[0]
        newline = line[0:tag_index+5] + chromosome + line[tag_index+14+len(chromosome):]
        updated_v2.write(newline)
    else:
        updated_v2.write(line)