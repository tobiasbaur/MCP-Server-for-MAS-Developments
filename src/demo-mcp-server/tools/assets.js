export{ bitcoin, gold }
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

//The actual tool function
async function bitcoin(args){

   const apiUrl = 'https://api.coindesk.com/v1/bpi/currentprice/USD.json'
   const json = await fetch(apiUrl)
                .then(response => response.json());
   //console.log(json);
    var result = json.bpi.USD.rate + " " +  json.bpi.USD.code
    return {
      content: [{ type: "text", text: `${result}` }],
    };
}


async function gold(args){
 const apiUrl = 'https://api.gold-api.com/price/XAU'
   const json = await fetch(apiUrl)
                .then(response => response.json());
   //console.log(json);
    var result = json.price + " USD"
    return {
      content: [{ type: "text", text: `${result}` }],
    };


}
