function startOrdersSocket(callback){

    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";

    const socket = new WebSocket(
        protocol + window.location.host + "/ws/orders/"
    );

    socket.onopen = () => console.log("🔥 WS conectado");
    socket.onclose = () => console.log("❌ WS fechado");
    socket.onerror = () => console.log("⚠️ WS erro");

    socket.onmessage = function(e){
        const data = JSON.parse(e.data);
        callback(data);
    };

    return socket;
}