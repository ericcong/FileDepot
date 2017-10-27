package boot;

import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.*;
import org.springframework.stereotype.*;
import org.springframework.ui.*;

import org.springframework.web.servlet.view.*;

import javax.servlet.http.*;
import org.springframework.http.*;
import org.springframework.web.client.*;
import org.springframework.boot.json.*;

import java.util.*;

import org.slf4j.*;

@CrossOrigin(origins="*")
@Controller
public class WebController {

    private static final Logger log = LoggerFactory.getLogger(WebController.class);
    private static final String fileDepotUrl = "http://.../lockers";
    private static final String jwtToken = "...";

    @RequestMapping(value="/viewfile", method=RequestMethod.GET)
    public RedirectView view(
    	@RequestParam(value="id", required=true) String id
    ) {
        log.info(id);
        String url = retrieve(id);
        log.info(url);
        return new RedirectView(url);
    }

    @RequestMapping(value="/uploadfile", method=RequestMethod.POST, consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> upload(
        @RequestBody String body
    ) {
        String locker = reserve(body);
        log.info(locker);
        HttpHeaders responseHeaders = new HttpHeaders();
        responseHeaders.setContentType(MediaType.APPLICATION_JSON);
        return new ResponseEntity<String>(locker, 
            responseHeaders, HttpStatus.OK);
    }

    private String reserve(String request) {
        Map<String, Object> m = JsonParserFactory.getJsonParser()
            .parseMap(request);
        // check file type
        // check file size
        // set expiration time
        // optionaly remove file name, so random name will be used        
        log.info(m.toString());

        HttpHeaders headers = new HttpHeaders();
        headers.set("FileDepot-jwt", jwtToken);
        HttpEntity<Map> entity = new HttpEntity<Map>(m, headers);

        log.info(entity.toString());

        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.postForEntity(
            fileDepotUrl, 
            entity,
            String.class);
        return response.getBody();
    }

    private String retrieve(String lockerId) {
        RestTemplate restTemplate = new RestTemplate();

        HttpHeaders headers = new HttpHeaders();
        headers.set("FileDepot-jwt", jwtToken);
        HttpEntity entity = new HttpEntity(headers);

        ResponseEntity<String> response = restTemplate.exchange(
            fileDepotUrl+"/"+lockerId, 
            HttpMethod.GET,
            entity,
            String.class);
        log.info(response.getBody());
        Map<String, Object> m = JsonParserFactory.getJsonParser()
            .parseMap(response.getBody());
        log.info(m.get("packages").toString());

        // API support multi-package per locker, here we use only one    
        return ((Map)((List)m.get("packages")).get(0)).get("download_url").toString();       
    }

}