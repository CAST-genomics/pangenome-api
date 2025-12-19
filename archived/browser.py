from flask import Flask,render_template, request, jsonify
import graph_plotter
import bandage_graph
import tempfile
import os

app = Flask(__name__,template_folder="templates")

@app.route("/")
def pangenomeDemo():
    return render_template('index.html')

@app.route('/generate-svg', methods=['POST'])
def process():
    inputSetting = request.get_json()
    
    gfa = inputSetting.get("gfa")
    exact_overlap = inputSetting.get("exact-overlap")
    debug_small_graphs = inputSetting.get("debug-small-graphs")
    min_node_length = inputSetting.get("minnodelength")
    node_seg_length = inputSetting.get("nodeseglen")
    edge_length = inputSetting.get("edgelen")
    node_len_per_mb = inputSetting.get("nodelenpermb")
    name_label = inputSetting.get("namelabel")
    
    setting = {
        "EXACT_OVERLAP": bool(exact_overlap), 
        "DEBUG_SMALL_GRAPHS": bool(debug_small_graphs),
        "MINNODELENGTH": float(min_node_length), 
        "NODESEGLEN": float(node_seg_length), 
        "EDGELEN": float(edge_length), 
        "NODELENPERMB": float(node_len_per_mb),
        "NAMELABEL": bool(name_label)
    }

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as subgraphGfaFile:
        subgraphGfaFile.write(gfa)
    
    with open(subgraphGfaFile.name, "r") as file:
        debugContent = file.read()
    
    pggraph = bandage_graph.PGGraph(subgraphGfaFile.name, setting)
    pggraph.BuildOGDFGraph()
    pggraph.LayoutGraph()
    graphPlotter = graph_plotter.GraphPlotter(pggraph, setting)
    svgFile = graphPlotter.BuildSvg()
    with open(svgFile, "r") as file:
        content = file.read()
    os.remove(subgraphGfaFile.name)
    os.remove(svgFile)
    return {"svg": content}



if __name__ == '__main__':
    app.run(debug=True)