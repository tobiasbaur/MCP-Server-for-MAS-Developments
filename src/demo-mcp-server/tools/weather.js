export{ weather }
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

async function weather(args){
   const apiUrl = "https://wttr.in/"  + encodeURIComponent(args.location)+ "?format=\"%t+%C+%h+%w\n\""
   const result = await fetch(apiUrl)
                .then(response => response.text());
     console.log(result)
    return {
      content: [{ type: "text", text: `${result}` }],
    };
}

weather({"location": "Munich"})